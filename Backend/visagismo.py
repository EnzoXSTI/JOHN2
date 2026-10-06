"""Rotas de catálogo, visagismo e agenda do Cortaê.

O módulo não depende do script experimental em ``Teste-main``: ele mantém os
dados no Firebird, protege as rotas pelo cookie já usado pelo projeto e deixa a
integração com OpenAI opcional até uma chave ser configurada no servidor.
"""

import base64
import json
import os
import re
import threading
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from flask import jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from main import app, conectar_banco
from barbearia import obter_usuario_logado, pegar_id_barbearia_alvo
from funcoes import enviar_aviso_email

try:
    from openai import OpenAI
except ImportError:  # Permite iniciar a API antes de instalar a dependência.
    OpenAI = None


EXTENSOES_PERMITIDAS = {'jpg', 'jpeg', 'png', 'webp'}
DIAS_SEMANA = ('segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo')
_schema_pronto = False
_schema_lock = threading.Lock()


def resposta_erro(texto, status=400):
    return jsonify({'mensagem': {'informacao': texto, 'tipo': 'erro'}}), status


def json_seguro(valor, padrao=None):
    if valor is None:
        return padrao if padrao is not None else {}
    if isinstance(valor, (dict, list)):
        return valor
    try:
        return json.loads(str(valor))
    except (TypeError, ValueError, json.JSONDecodeError):
        return padrao if padrao is not None else {}


def normalizar(valor):
    return re.sub(r'[^a-z0-9]+', ' ', str(valor or '').lower()).strip()


def garantir_pastas():
    for chave in ('VISAGISMO_CORTES_FOLDER', 'VISAGISMO_FOTOS_FOLDER', 'VISAGISMO_RESULTADOS_FOLDER'):
        os.makedirs(app.config[chave], exist_ok=True)


def objeto_existe(cursor, tipo, nome):
    """Verifica no catálogo do Firebird se uma tabela ou sequence já existe."""
    nome = str(nome).upper()

    if tipo == 'tabela':
        cursor.execute('''
                       SELECT 1
                       FROM RDB$RELATIONS
                       WHERE TRIM(RDB$RELATION_NAME) = ?
                       ''', (nome,))
    elif tipo == 'sequence':
        cursor.execute('''
                       SELECT 1
                       FROM RDB$GENERATORS
                       WHERE TRIM(RDB$GENERATOR_NAME) = ?
                       ''', (nome,))
    else:
        raise ValueError(f'Tipo de objeto inválido: {tipo}')

    return cursor.fetchone() is not None


def criar_tabela_se_nao_existir(cursor, nome, sql):
    """Cria uma tabela somente quando ela ainda não existe no Firebird."""
    if not objeto_existe(cursor, 'tabela', nome):
        cursor.execute(sql)


def criar_sequence_se_nao_existir(cursor, nome):
    """Cria uma sequence somente quando ela ainda não existe no Firebird."""
    if not objeto_existe(cursor, 'sequence', nome):
        cursor.execute(f'CREATE SEQUENCE {nome}')


def garantir_estrutura():
    """Cria as estruturas do módulo somente quando elas ainda não existem."""
    global _schema_pronto
    if _schema_pronto:
        return

    with _schema_lock:
        if _schema_pronto:
            return

        con = conectar_banco()
        cursor = con.cursor()

        try:
            criar_tabela_se_nao_existir(cursor, 'CORTE_VISAGISMO', '''
                                                                   CREATE TABLE CORTE_VISAGISMO (
                                                                                                    ID_CORTE INTEGER NOT NULL PRIMARY KEY,
                                                                                                    ID_USUARIO INTEGER,
                                                                                                    NOME VARCHAR(150) NOT NULL,
                                                                                                    DESCRICAO BLOB SUB_TYPE TEXT,
                                                                                                    CATEGORIA VARCHAR(30) NOT NULL,
                                                                                                    IMAGEM_ROTA VARCHAR(255),
                                                                                                    ATIVO SMALLINT DEFAULT 1 NOT NULL,
                                                                                                    CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                                                                   )
                                                                   ''')

            criar_tabela_se_nao_existir(cursor, 'VISAGISMO_SESSAO', '''
                                                                    CREATE TABLE VISAGISMO_SESSAO (
                                                                                                      ID_VISAGISMO INTEGER NOT NULL PRIMARY KEY,
                                                                                                      ID_USUARIO INTEGER NOT NULL,
                                                                                                      ID_BARBEARIA INTEGER,
                                                                                                      SERVICOS_JSON BLOB SUB_TYPE TEXT,
                                                                                                      FOTO_ROTA VARCHAR(255),
                                                                                                      ANALISE_JSON BLOB SUB_TYPE TEXT,
                                                                                                      CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                                                                    )
                                                                    ''')

            criar_tabela_se_nao_existir(cursor, 'AGENDAMENTO', '''
                                                               CREATE TABLE AGENDAMENTO (
                                                                                            ID_AGENDAMENTO INTEGER NOT NULL PRIMARY KEY,
                                                                                            ID_USUARIO INTEGER NOT NULL,
                                                                                            ID_BARBEARIA INTEGER NOT NULL,
                                                                                            ID_FUNCIONARIO INTEGER,
                                                                                            INICIO_EM TIMESTAMP NOT NULL,
                                                                                            FIM_EM TIMESTAMP NOT NULL,
                                                                                            SERVICOS_JSON BLOB SUB_TYPE TEXT,
                                                                                            ID_CORTE INTEGER,
                                                                                            ID_VISAGISMO INTEGER,
                                                                                            STATUS VARCHAR(20) DEFAULT 'agendado' NOT NULL,
                                                                                            CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                                                               )
                                                               ''')

            criar_tabela_se_nao_existir(cursor, 'AGENDAMENTO_HISTORICO', '''
                                                                          CREATE TABLE AGENDAMENTO_HISTORICO (
                                                                              ID_HISTORICO INTEGER NOT NULL PRIMARY KEY,
                                                                              ID_AGENDAMENTO INTEGER NOT NULL,
                                                                              STATUS VARCHAR(20) NOT NULL,
                                                                              ID_USUARIO_RESPONSAVEL INTEGER,
                                                                              REGISTRADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                                                                          )
                                                                          ''')

            for sequencia in (
                    'SEQ_CORTE_VISAGISMO',
                    'SEQ_VISAGISMO_SESSAO',
                    'SEQ_AGENDAMENTO',
                    'SEQ_AGENDAMENTO_HISTORICO'
            ):
                criar_sequence_se_nao_existir(cursor, sequencia)

            # Migração: bancos criados antes da escolha de barbeiro não têm a coluna.
            cursor.execute('''SELECT 1 FROM RDB$RELATION_FIELDS
                              WHERE TRIM(RDB$RELATION_NAME) = 'AGENDAMENTO'
                                AND TRIM(RDB$FIELD_NAME) = 'ID_FUNCIONARIO' ''')
            if cursor.fetchone() is None:
                cursor.execute('ALTER TABLE AGENDAMENTO ADD ID_FUNCIONARIO INTEGER')

            # A simulação gerada por IA fica registrada na sessão para o agendamento exibir.
            for coluna, tipo_col in (('ID_CORTE_SIMULADO', 'INTEGER'), ('RESULTADO_ROTA', 'VARCHAR(255)')):
                cursor.execute('''SELECT 1 FROM RDB$RELATION_FIELDS
                                  WHERE TRIM(RDB$RELATION_NAME) = 'VISAGISMO_SESSAO'
                                    AND TRIM(RDB$FIELD_NAME) = ? ''', (coluna,))
                if cursor.fetchone() is None:
                    cursor.execute(f'ALTER TABLE VISAGISMO_SESSAO ADD {coluna} {tipo_col}')

            # Campo GENERO na tabela USUARIO para filtro de cortes por gênero
            cursor.execute('''SELECT 1 FROM RDB$RELATION_FIELDS
                              WHERE TRIM(RDB$RELATION_NAME) = 'USUARIO'
                                AND TRIM(RDB$FIELD_NAME) = 'GENERO' ''')
            if cursor.fetchone() is None:
                cursor.execute('ALTER TABLE USUARIO ADD GENERO VARCHAR(10)')

            # Campo GENERO na tabela CORTE_VISAGISMO para filtro de cortes por gênero
            cursor.execute('''SELECT 1 FROM RDB$RELATION_FIELDS
                              WHERE TRIM(RDB$RELATION_NAME) = 'CORTE_VISAGISMO'
                                AND TRIM(RDB$FIELD_NAME) = 'GENERO' ''')
            if cursor.fetchone() is None:
                cursor.execute('ALTER TABLE CORTE_VISAGISMO ADD GENERO VARCHAR(10)')

            # Campos PIX/Arkhe na tabela PERSONALIZACAO
            for coluna, tipo_col in (('CHAVE_PIX', 'VARCHAR(100)'), ('ARKHE_CLIENT_ID', 'VARCHAR(100)'), ('ARKHE_CLIENT_SECRET', 'VARCHAR(200)')):
                cursor.execute('''SELECT 1 FROM RDB$RELATION_FIELDS
                                  WHERE TRIM(RDB$RELATION_NAME) = 'PERSONALIZACAO'
                                    AND TRIM(RDB$FIELD_NAME) = ? ''', (coluna,))
                if cursor.fetchone() is None:
                    cursor.execute(f'ALTER TABLE PERSONALIZACAO ADD {coluna} {tipo_col}')

            # Unificação: a tabela legada AGENDAMENTOS (sem barbearia/datas, sem uso
            # no código) é removida quando vazia. Com linhas, elas são migradas para
            # AGENDAMENTO resolvendo a barbearia pelo funcionário vinculado.
            if objeto_existe(cursor, 'tabela', 'AGENDAMENTOS'):
                cursor.execute('SELECT COUNT(*) FROM AGENDAMENTOS')
                if (cursor.fetchone() or [0])[0] == 0:
                    cursor.execute('DROP TABLE AGENDAMENTOS')
                else:
                    cursor.execute('''SELECT ID_AGENDAMENTO, ID_USUARIO, ID_SERVICO,
                                      ID_FUNCIONARIO, CORTE, HORARIO FROM AGENDAMENTOS''')
                    for leg in cursor.fetchall():
                        cursor.execute('''SELECT D.ID_USUARIO FROM FUNCIONARIO_DIA FD
                                          INNER JOIN DIAS_DE_SERVICO D ON D.ID_DIA = FD.ID_DIA
                                          WHERE FD.ID_FUNCIONARIO = ?''', (leg[3],))
                        barb = cursor.fetchone()
                        if not barb:
                            continue
                        try:
                            cursor.execute('''INSERT INTO AGENDAMENTO
                                              (ID_AGENDAMENTO, ID_USUARIO, ID_BARBEARIA, ID_FUNCIONARIO,
                                               INICIO_EM, FIM_EM, SERVICOS_JSON, ID_CORTE, STATUS)
                                              VALUES (NEXT VALUE FOR SEQ_AGENDAMENTO, ?, ?, ?, ?, ?, ?, ?, 'agendado')''',
                                           (leg[1], barb[0], leg[3], leg[5], leg[5],
                                            json.dumps([leg[2]]) if leg[2] is not None else '[]', leg[4]))
                            cursor.execute('DELETE FROM AGENDAMENTOS WHERE ID_AGENDAMENTO = ?', (leg[0],))
                        except Exception:
                            continue
                    cursor.execute('SELECT COUNT(*) FROM AGENDAMENTOS')
                    if (cursor.fetchone() or [0])[0] == 0:
                        cursor.execute('DROP TABLE AGENDAMENTOS')

            con.commit()
            _schema_pronto = True

        except Exception:
            con.rollback()
            raise

        finally:
            cursor.close()
            con.close()


# Função removida: as sequences são usadas diretamente nos inserts com NEXT VALUE FOR


def ids_servicos_da_requisicao(dados):
    valor = dados.get('ids_servicos') or dados.get('servicos') or []
    if isinstance(valor, str):
        decodificado = json_seguro(valor, None)
        valor = decodificado if isinstance(decodificado, list) else [item for item in valor.split(',') if item.strip()]
    if not isinstance(valor, list):
        return []
    try:
        return sorted({int(item) for item in valor})
    except (TypeError, ValueError):
        return []


def carregar_servicos(cursor, id_barbearia, ids_servicos):
    if not ids_servicos:
        return []
    marcadores = ','.join('?' for _ in ids_servicos)
    cursor.execute(f'''
        SELECT ID_SERVICO, NOME_SERVICO, DURACAO, GENERO
        FROM SERVICO
        WHERE ID_USUARIO = ? AND ID_SERVICO IN ({marcadores})
    ''', [id_barbearia, *ids_servicos])
    encontrados = cursor.fetchall()
    if len(encontrados) != len(ids_servicos):
        return []
    return [
        {'id_servico': linha[0], 'nome': linha[1], 'duracao': int(linha[2] or 0),
         'genero': str(linha[3] or 'unissex').strip().lower()}
        for linha in encontrados
    ]


def servico_indica_corte_de_cabelo(nome):
    """Distingue corte de cabelo de um simples corte de barba."""
    nome = normalizar(nome)
    if any(palavra in nome for palavra in ('cabelo', 'pezinho', 'lavagem', 'degrade')):
        return True
    if 'corte' not in nome:
        return False
    if 'barba' not in nome and 'bigode' not in nome:
        return True
    # Serviço único como "corte e barba" também cobre cabelo e barba.
    return bool(re.search(r'\bcorte\s+(e|com)\s+(a\s+)?barba\b', nome))


def categoria_para_servicos(servicos):
    nomes = ' '.join(normalizar(servico['nome']) for servico in servicos)
    tem_barba = 'barba' in nomes or 'bigode' in nomes
    tem_cabelo = any(palavra in nomes for palavra in ('cabelo', 'pezinho', 'lavagem', 'degrade'))
    tem_corte_cabelo = any(servico_indica_corte_de_cabelo(servico['nome']) for servico in servicos)
    tem_pintar = 'pintar' in nomes or 'color' in nomes or 'tinta' in nomes
    # Tratamentos que precisam de visagismo mas não são "corte"
    tem_tratamento_cabelo = any(palavra in nomes for palavra in ('progressiva', 'alisamento', 'mega hair', 'mega-hair', 'mega', 'hidratacao', 'cauterizacao', 'botox', 'reconstrucao', 'selagem', 'escova'))
    
    if tem_barba and (tem_cabelo or tem_corte_cabelo or tem_tratamento_cabelo):
        return 'barba_cabelo'
    if tem_barba:
        return 'barba'
    if tem_pintar and tem_corte_cabelo:
        return 'corte_pintura'
    if tem_pintar:
        return 'pintura'
    # Se tem tratamento de cabelo, usa categoria 'cabelo' para buscar cortes
    if tem_tratamento_cabelo or tem_cabelo or tem_corte_cabelo:
        return 'cabelo'
    return 'cabelo'


def categoria_para_busca(servicos, genero=None):
    """Retorna a categoria de cortes a ser buscada no banco.
    
    O banco tem cortes com categorias: masculino, feminino, barba, barba_cabelo.
    Esta função mapeia o serviço selecionado para a categoria correta.
    """
    nomes = ' '.join(normalizar(servico['nome']) for servico in servicos)
    tem_barba = 'barba' in nomes or 'bigode' in nomes
    tem_cabelo = any(palavra in nomes for palavra in ('cabelo', 'pezinho', 'lavagem', 'degrade'))
    tem_corte_cabelo = any(servico_indica_corte_de_cabelo(servico['nome']) for servico in servicos)
    tem_pintar = 'pintar' in nomes or 'color' in nomes or 'tinta' in nomes
    tem_tratamento_cabelo = any(palavra in nomes for palavra in ('progressiva', 'alisamento', 'mega hair', 'mega-hair', 'mega', 'hidratacao', 'cauterizacao', 'botox', 'reconstrucao', 'selagem', 'escova'))
    
    # Barba
    if tem_barba and (tem_cabelo or tem_corte_cabelo or tem_tratamento_cabelo):
        return 'barba_cabelo'
    if tem_barba:
        return 'barba'
    
    # Pintura
    if tem_pintar and tem_corte_cabelo:
        return 'corte_pintura'
    if tem_pintar:
        return 'pintura'
    
    # Corte de cabelo - usa o gênero do usuário para filtrar
    if tem_tratamento_cabelo or tem_cabelo or tem_corte_cabelo:
        if genero == 'feminino':
            return 'feminino'
        elif genero == 'masculino':
            return 'masculino'
        else:
            # Sem gênero definido, busca em ambas as categorias
            return None  # None significa buscar em todas as categorias de cabelo
    
    return None  # Busca em todas as categorias


def precisa_visagismo(servicos):
    """Verifica se a seleção de serviços precisa de análise de visagismo.
    Todos os serviços precisam de visagismo para mostrar a simulação ao usuário."""
    return True


def so_pintar_cabelo(servicos):
    """Verifica se a seleção é APENAS 'pintar cabelo' (sem corte, sem barba, sem outros tratamentos)."""
    nomes = ' '.join(normalizar(servico['nome']) for servico in servicos)
    tem_pintar = 'pintar' in nomes or 'color' in nomes or 'tinta' in nomes
    tem_corte = 'corte' in nomes or 'pezinho' in nomes or 'degrade' in nomes
    tem_barba = 'barba' in nomes or 'bigode' in nomes
    tem_tratamento = any(palavra in nomes for palavra in ('progressiva', 'alisamento', 'mega hair', 'mega-hair', 'mega', 'hidratacao', 'cauterizacao', 'botox', 'reconstrucao', 'selagem', 'escova'))
    tem_cabelo = 'cabelo' in nomes or 'lavagem' in nomes
    
    # É só pintar cabelo se tem pintar mas NÃO tem corte, barba, nem outros tratamentos
    return tem_pintar and not tem_corte and not tem_barba and not tem_tratamento and not (tem_cabelo and not tem_pintar)


def generos_para_filtro_servicos(servicos):
    """Retorna os públicos explícitos dos serviços selecionados.

    O filtro usa o campo ``SERVICO.GENERO``, e nunca palavras no nome: uma
    pessoa pode dar qualquer nome comercial ao serviço sem alterar o catálogo.
    Serviços unissex não restringem os cortes disponíveis.
    """
    generos = {
        str(servico.get('genero') or 'unissex').strip().lower()
        for servico in servicos
    }
    return tuple(genero for genero in ('masculino', 'feminino') if genero in generos)


def categorias_catalogo_para_servicos(servicos):
    """Resolve as categorias reais usadas no catálogo de cortes.

    O serviço de cabelo é genérico, porém o catálogo atual guarda seus cortes
    nas categorias ``masculino`` e ``feminino``. Por isso não podemos buscar
    apenas a categoria ``cabelo``: ela faria o catálogo voltar vazio mesmo
    quando há cortes disponíveis.
    """
    generos = generos_para_filtro_servicos(servicos)
    categorias_cabelo = generos or ('masculino', 'feminino', 'cabelo')
    categoria = categoria_para_servicos(servicos)

    # Combinações de serviços não podem depender de uma categoria especial
    # existir no catálogo. Por exemplo, "corte + pintar cabelo" deve exibir
    # os cortes de cabelo normais mesmo quando não houver item cadastrado em
    # ``corte_pintura``. Para barba + cabelo, mantemos também os estilos
    # específicos de barba/cabelo, quando existirem.
    if categoria in ('barba_cabelo', 'corte_pintura'):
        return tuple(dict.fromkeys((categoria, *categorias_cabelo)))
    if categoria == 'pintura':
        return categorias_cabelo
    if categoria == 'cabelo':
        return categorias_cabelo
    return (categoria,)


def salvar_arquivo(arquivo, pasta, prefixo):
    if not arquivo or not arquivo.filename:
        raise ValueError('Envie uma imagem.')
    extensao = Path(secure_filename(arquivo.filename)).suffix.lower().lstrip('.')
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValueError('Formato inválido. Envie JPG, PNG ou WEBP.')
    arquivo.stream.seek(0)
    conteudo = arquivo.read(app.config['MAX_VISAGISMO_IMAGE_BYTES'] + 1)
    if not conteudo or len(conteudo) > app.config['MAX_VISAGISMO_IMAGE_BYTES']:
        raise ValueError('A imagem deve ter até 10 MB.')
    nome = f'{prefixo}_{uuid4().hex}.{extensao}'
    caminho = os.path.join(pasta, nome)
    with open(caminho, 'wb') as destino:
        destino.write(conteudo)
    return nome, caminho


def baixar_imagem_remota(url, pasta, prefixo):
    """Importa uma imagem HTTPS da API de imagens escolhida pela barbearia."""
    destino_url = urlparse(str(url or ''))
    if destino_url.scheme != 'https' or not destino_url.netloc:
        raise ValueError('A URL da imagem deve usar HTTPS.')
    requisicao = Request(destino_url.geturl(), headers={'User-Agent': 'Cortae/1.0'})
    with urlopen(requisicao, timeout=20) as resposta:
        final = urlparse(resposta.geturl())
        if final.scheme != 'https':
            raise ValueError('O redirecionamento da imagem não é seguro.')
        tipo = resposta.headers.get_content_type()
        extensoes = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}
        extensao = extensoes.get(tipo)
        conteudo = resposta.read(app.config['MAX_VISAGISMO_IMAGE_BYTES'] + 1)
    if not extensao or not conteudo or len(conteudo) > app.config['MAX_VISAGISMO_IMAGE_BYTES']:
        raise ValueError('A URL não retornou uma imagem JPG, PNG ou WEBP de até 10 MB.')
    nome = f'{prefixo}_{uuid4().hex}.{extensao}'
    caminho = os.path.join(pasta, nome)
    with open(caminho, 'wb') as destino:
        destino.write(conteudo)
    return nome, caminho


def url_corte(nome):
    if not nome:
        return None
    # Se for uma URL externa (http/https), retornar diretamente
    if nome.startswith('http://') or nome.startswith('https://'):
        return nome
    # Caso contrário, é um arquivo local
    return f'/uploads/visagismo/cortes/{nome}'


def serializar_corte(linha):
    return {
        'id_corte': linha[0], 'nome': linha[1], 'descricao': str(linha[2] or ''),
        'categoria': linha[3], 'imagem_url': url_corte(linha[4]), 'ativo': bool(linha[5]),
        'genero': linha[6] if len(linha) > 6 else None
    }


def pode_gerenciar_catalogo(usuario):
    return usuario and int(usuario.get('tipo', -1)) in (0, 2)


@app.route('/visagismo/cortes', methods=['GET'])
def listar_cortes_visagismo():
    try:
        garantir_estrutura()
        id_barbearia = request.args.get('id_barbearia', type=int)
        ids_servicos = ids_servicos_da_requisicao(request.args)
        categoria = request.args.get('categoria')
        con = conectar_banco(); cursor = con.cursor()
        try:
            servicos = carregar_servicos(cursor, id_barbearia, ids_servicos) if id_barbearia else []
            if id_barbearia and ids_servicos and not servicos:
                return resposta_erro('Serviços inválidos para esta barbearia.', 400)
            
            categorias = (categoria,) if categoria else (categorias_catalogo_para_servicos(servicos) if servicos else ())
            generos_servico = generos_para_filtro_servicos(servicos)
            
            # Busca todos os cortes ativos, filtrando por gênero se necessário
            sql = "SELECT ID_CORTE, NOME, DESCRICAO, CATEGORIA, IMAGEM_ROTA, ATIVO, GENERO"
            sql += " FROM CORTE_VISAGISMO WHERE ATIVO = 1"
            parametros = []
            
            # Um serviço de cabelo pode corresponder às categorias masculina,
            # feminina ou à categoria legada genérica ``cabelo``.
            if categorias:
                marcadores = ','.join('?' for _ in categorias)
                sql += f" AND CATEGORIA IN ({marcadores})"
                parametros.extend(categorias)
            
            # Filtra pelo serviço escolhido, nunca pelo gênero do usuário logado.
            if generos_servico:
                marcadores = ','.join('?' for _ in generos_servico)
                # Para barba, não aceitamos itens sem gênero definido: esses
                # estilos são exclusivos do catálogo masculino.
                if categoria_para_servicos(servicos) in ('barba', 'barba_cabelo'):
                    sql += f" AND GENERO IN ({marcadores})"
                else:
                    sql += f" AND (GENERO IN ({marcadores}) OR GENERO IS NULL)"
                parametros.extend(generos_servico)
            
            sql += " ORDER BY NOME"
            cursor.execute(sql, parametros)
            cortes = [serializar_corte(linha) for linha in cursor.fetchall()]
            
            return jsonify({'mensagem': {'informacao': 'Cortes listados.', 'tipo': 'sucesso'},
                            'categoria': categoria or (categorias[0] if len(categorias) == 1 else 'cabelo'),
                            'cortes': cortes})
        finally:
            cursor.close(); con.close()
    except Exception as erro:
        return resposta_erro(f'Erro ao listar cortes: {erro}', 500)


@app.route('/visagismo/cortes', methods=['POST'])
def criar_corte_visagismo():
    usuario = obter_usuario_logado()
    if not pode_gerenciar_catalogo(usuario):
        return resposta_erro('Apenas administradores ou barbearias podem administrar cortes.', 403)
    try:
        garantir_estrutura(); garantir_pastas()
        dados = request.form if request.form else (request.get_json(silent=True) or {})
        nome = str(dados.get('nome', '')).strip()
        descricao = str(dados.get('descricao', '')).strip()
        categoria = str(dados.get('categoria', '')).strip().lower()
        genero = str(dados.get('genero', '')).strip().lower()
        if genero and genero not in ['masculino', 'feminino', 'unissex']:
            return resposta_erro('Gênero inválido. Use: masculino, feminino ou unissex.')
        if not nome or categoria not in {'cabelo', 'barba', 'barba_cabelo', 'corte_pintura', 'pintura'}:
            return resposta_erro('Informe nome e uma categoria válida: cabelo, barba, barba_cabelo, corte_pintura ou pintura.')
        imagem = request.files.get('imagem')
        imagem_url = dados.get('imagem_url')
        if imagem:
            arquivo, _ = salvar_arquivo(imagem, app.config['VISAGISMO_CORTES_FOLDER'], 'corte')
        elif imagem_url:
            arquivo, _ = baixar_imagem_remota(imagem_url, app.config['VISAGISMO_CORTES_FOLDER'], 'corte')
        else:
            return resposta_erro('Envie a imagem de exemplo ou uma imagem_url HTTPS.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            # Verificar se já existe um corte com o mesmo nome
            cursor.execute('SELECT ID_CORTE FROM CORTE_VISAGISMO WHERE LOWER(TRIM(NOME)) = ?', (nome.lower(),))
            if cursor.fetchone():
                return resposta_erro('Já existe um corte com este nome.')
            
            cursor.execute('''INSERT INTO CORTE_VISAGISMO
                                  (ID_CORTE, ID_USUARIO, NOME, DESCRICAO, CATEGORIA, IMAGEM_ROTA, GENERO)
                              VALUES (NEXT VALUE FOR SEQ_CORTE_VISAGISMO, ?, ?, ?, ?, ?, ?)
                              RETURNING ID_CORTE''',
                           (usuario['id_usuario'], nome, descricao, categoria, arquivo, genero if genero else None))
            id_corte = cursor.fetchone()[0]
            con.commit()
            return jsonify({'mensagem': {'informacao': 'Corte adicionado.', 'tipo': 'sucesso'},
                            'corte': {'id_corte': id_corte, 'nome': nome, 'descricao': descricao,
                                      'categoria': categoria, 'imagem_url': url_corte(arquivo)}}), 201
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Erro ao criar corte: {erro}', 500)


@app.route('/visagismo/cortes/<int:id_corte>', methods=['PUT'])
def editar_corte_visagismo(id_corte):
    usuario = obter_usuario_logado()
    if not pode_gerenciar_catalogo(usuario):
        return resposta_erro('Sem permissão para editar cortes.', 403)
    try:
        garantir_estrutura(); garantir_pastas()
        dados = request.form if request.form else (request.get_json(silent=True) or {})
        nome = str(dados.get('nome', '')).strip(); descricao = str(dados.get('descricao', '')).strip()
        categoria = str(dados.get('categoria', '')).strip().lower()
        genero = str(dados.get('genero', '')).strip().lower()
        if genero and genero not in ['masculino', 'feminino', 'unissex']:
            return resposta_erro('Gênero inválido. Use: masculino, feminino ou unissex.')
        if not nome or categoria not in {'cabelo', 'barba', 'barba_cabelo', 'corte_pintura', 'pintura'}:
            return resposta_erro('Informe nome e categoria válida: cabelo, barba, barba_cabelo, corte_pintura ou pintura.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            # Verificar se já existe outro corte com o mesmo nome
            cursor.execute('SELECT ID_CORTE FROM CORTE_VISAGISMO WHERE LOWER(TRIM(NOME)) = ? AND ID_CORTE <> ?', (nome.lower(), id_corte))
            if cursor.fetchone():
                return resposta_erro('Já existe outro corte com este nome.')
            
            cursor.execute('SELECT IMAGEM_ROTA FROM CORTE_VISAGISMO WHERE ID_CORTE = ?', (id_corte,))
            anterior = cursor.fetchone()
            if not anterior:
                return resposta_erro('Corte não encontrado.', 404)
            imagem_nome = anterior[0]
            if request.files.get('imagem') or dados.get('imagem_url'):
                imagem_nome, _ = (salvar_arquivo(request.files['imagem'], app.config['VISAGISMO_CORTES_FOLDER'], 'corte')
                                  if request.files.get('imagem') else
                                  baixar_imagem_remota(dados.get('imagem_url'), app.config['VISAGISMO_CORTES_FOLDER'], 'corte'))
                if anterior[0]:
                    caminho_antigo = os.path.join(app.config['VISAGISMO_CORTES_FOLDER'], anterior[0])
                    if os.path.isfile(caminho_antigo): os.remove(caminho_antigo)
            cursor.execute('''UPDATE CORTE_VISAGISMO SET NOME=?, DESCRICAO=?, CATEGORIA=?, IMAGEM_ROTA=?, GENERO=?
                              WHERE ID_CORTE=?''', (nome, descricao, categoria, imagem_nome, genero if genero else None, id_corte))
            con.commit()
            return jsonify({'mensagem': {'informacao': 'Corte atualizado.', 'tipo': 'sucesso'}})
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Erro ao editar corte: {erro}', 500)


@app.route('/visagismo/cortes/<int:id_corte>', methods=['DELETE'])
def excluir_corte_visagismo(id_corte):
    usuario = obter_usuario_logado()
    if not pode_gerenciar_catalogo(usuario):
        return resposta_erro('Sem permissão para excluir cortes.', 403)
    try:
        garantir_estrutura()
        con = conectar_banco(); cursor = con.cursor()
        try:
            cursor.execute('SELECT IMAGEM_ROTA FROM CORTE_VISAGISMO WHERE ID_CORTE=?', (id_corte,))
            corte = cursor.fetchone()
            if not corte: return resposta_erro('Corte não encontrado.', 404)
            # Exclusão lógica preserva escolhas e agendamentos antigos.
            cursor.execute('UPDATE CORTE_VISAGISMO SET ATIVO = 0 WHERE ID_CORTE=?', (id_corte,))
            con.commit()
            return jsonify({'mensagem': {'informacao': 'Corte removido do catálogo.', 'tipo': 'sucesso'}})
        finally:
            cursor.close(); con.close()
    except Exception as erro:
        return resposta_erro(f'Erro ao excluir corte: {erro}', 500)


def motivo_sem_ia():
    """Explica por que a análise caiu no modo sem IA (sem vazar a chave)."""
    if OpenAI is None:
        return 'Biblioteca openai não instalada no servidor. Rode: pip install -r requirements.txt'
    if not (app.config.get('OPENAI_API_KEY') or '').strip():
        return 'OPENAI_API_KEY ausente no servidor. Confira Backend/.env e reinicie o Flask.'
    return ''


def traduzir_erro_openai(erro):
    texto = f'{getattr(erro, "status_code", "")} {erro}'.lower()
    if 'expired' in texto:
        return 'Chave da OpenAI expirada (a própria API retornou expired_secret_key). Gere uma nova em platform.openai.com > API keys e troque no Backend/.env.'
    if '401' in texto or 'incorrect api key' in texto or 'invalid api key' in texto:
        return 'Chave da OpenAI rejeitada (401). Confira se a OPENAI_API_KEY é válida e não é uma chave de teste.'
    if '404' in texto or 'model_not_found' in texto or 'model not found' in texto:
        return (f'Modelo não encontrado na OpenAI. Modelo pedido: '
                f'{app.config.get("VISAGISMO_ANALYSIS_MODEL")}/{app.config.get("VISAGISMO_IMAGE_MODEL")}. '
                'Ajuste VISAGISMO_ANALYSIS_MODEL (ex: gpt-4o-mini) e VISAGISMO_IMAGE_MODEL (ex: gpt-image-1).')
    if '429' in texto or 'quota' in texto or 'insufficient_quota' in texto:
        return 'Cota da OpenAI esgotada ou limite excedido (429). Verifique billing/limites da chave.'
    return f'Falha na OpenAI: {erro}'


def analisar_com_ia(caminho_foto, cortes, categoria):
    """Espelha Teste-main: analisa a foto real do usuário via IA e só aceita IDs do catálogo."""
    if OpenAI is None:
        raise RuntimeError(motivo_sem_ia())
    chave = (app.config.get('OPENAI_API_KEY') or '').strip()
    if not chave:
        raise RuntimeError(motivo_sem_ia())
    catalogo = '\n'.join(
        f"ID: {c['id_corte']} | NOME: {c['nome']} | TAGS: {c.get('categoria') or 'nenhuma'} | DESCRICAO: {c.get('descricao') or ''}"
        for c in cortes
    )
    with open(caminho_foto, 'rb') as arquivo:
        imagem_b64 = base64.b64encode(arquivo.read()).decode('ascii')
    prompt = f'''Você é um especialista em visagismo para o sistema Cortaê.
Analise a fotografia enviada pelo usuário (serviço: {categoria}).
Use EXCLUSIVAMENTE os estilos existentes no catálogo.
CATÁLOGO:
{catalogo}
REGRAS IMPORTANTES:
1. Não invente cortes.
2. Não crie IDs.
3. O ID recomendado precisa existir no catálogo.
4. Recomende no máximo 3 estilos.
5. Considere somente estilos visualmente possíveis.
6. Observe o cabelo que realmente existe na fotografia.
7. Não recomende um estilo que dependa obrigatoriamente de cabelo inexistente quando isso inviabilizar o resultado.
8. Não identifique raça.
9. Não identifique etnia.
10. Não tente identificar a pessoa.
11. Não faça diagnóstico médico.
12. Não faça julgamentos sobre aparência.
13. Não use características pessoais sensíveis.
14. Analise apenas características relevantes ao cabelo e à escolha do penteado.
IMPORTANTE SOBRE A GERAÇÃO:
O sistema posteriormente fará uma simulação editando a foto do usuário.
Portanto, uma recomendação não deve pressupor que a IA possa simplesmente inventar cabelo onde não existe.
Retorne SOMENTE JSON válido no formato:
{{"observacoes": "observação curta", "cabelo_atual": "descrição objetiva do cabelo visível na foto",
"recomendacoes": [{{"id_corte": 1, "nome": "NOME_EXATO_DO_CATALOGO", "motivo": "motivo", "compativel_com_cabelo_existente": true}}]}}'''
    try:
        resposta = OpenAI(api_key=chave).responses.create(
            model=app.config['VISAGISMO_ANALYSIS_MODEL'],
            input=[{'role': 'user', 'content': [
                {'type': 'input_text', 'text': prompt},
                {'type': 'input_image', 'image_url': 'data:image/jpeg;base64,' + imagem_b64}
            ]}]
        )
    except Exception as erro:
        raise RuntimeError(traduzir_erro_openai(erro)) from erro
    texto = resposta.output_text.strip()
    texto = re.sub(r'^```(?:json)?\s*|\s*```$', '', texto, flags=re.I).strip()
    analise = json.loads(texto)
    # Valida como no Teste-main: descarta IDs inventados e limita a 3.
    por_id = {int(c['id_corte']): c for c in cortes}
    validas = []
    for item in analise.get('recomendacoes', []):
        try:
            id_corte = int(item.get('id_corte', item.get('id', '')))
        except (TypeError, ValueError):
            continue
        corte = por_id.get(id_corte)
        if corte is None or id_corte in {v['id_corte'] for v in validas}:
            continue
        validas.append({
            'id_corte': id_corte,
            'nome': corte['nome'],
            'motivo': str(item.get('motivo', '')),
            'compativel_com_cabelo_existente': bool(item.get('compativel_com_cabelo_existente', True)),
        })
        if len(validas) >= 3:
            break
    if not validas:
        raise RuntimeError('A IA não retornou nenhuma recomendação válida do catálogo.')
    analise['recomendacoes'] = validas
    return analise


@app.route('/visagismo/status', methods=['GET'])
def status_visagismo():
    """Diagnóstico rápido: mostra se a chave chega na rota, sem expor a chave."""
    chave = (app.config.get('OPENAI_API_KEY') or '').strip()
    return jsonify({
        'mensagem': {'informacao': 'Diagnóstico do visagismo.', 'tipo': 'sucesso'},
        'openai_key_configurada': bool(chave),
        'openai_key_prefixo': (chave[:7] + '...') if len(chave) >= 7 else None,
        'openai_lib_ok': OpenAI is not None,
        'analysis_model': app.config.get('VISAGISMO_ANALYSIS_MODEL'),
        'image_model': app.config.get('VISAGISMO_IMAGE_MODEL'),
        'motivo_sem_ia': motivo_sem_ia() or None,
    })


@app.route('/visagismo/analisar', methods=['POST'])
def analisar_visagismo():
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para usar o visagismo.', 401)
    try:
        garantir_estrutura(); garantir_pastas()
        id_barbearia = request.form.get('id_barbearia', type=int)
        ids_servicos = ids_servicos_da_requisicao(request.form)
        if not id_barbearia or not ids_servicos: return resposta_erro('Escolha a barbearia e ao menos um serviço.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            servicos = carregar_servicos(cursor, id_barbearia, ids_servicos)
            if not servicos: return resposta_erro('Serviços inválidos para a barbearia.', 400)
            categoria = categoria_para_servicos(servicos)
            categorias = categorias_catalogo_para_servicos(servicos)
            generos_servico = generos_para_filtro_servicos(servicos)
            
            # Função para buscar cortes com fallback de categoria
            def buscar_cortes(categorias_busca):
                marcadores = ','.join('?' for _ in categorias_busca)
                sql_cortes = '''SELECT ID_CORTE, NOME, DESCRICAO, CATEGORIA, IMAGEM_ROTA, ATIVO, GENERO
                                FROM CORTE_VISAGISMO WHERE ATIVO=1 AND CATEGORIA IN (''' + marcadores + ')'
                parametros_cortes = list(categorias_busca)
                if generos_servico:
                    if categoria in ('barba', 'barba_cabelo'):
                        sql_cortes += ' AND GENERO IN (' + ','.join('?' for _ in generos_servico) + ')'
                    else:
                        sql_cortes += ' AND (GENERO IN (' + ','.join('?' for _ in generos_servico) + ') OR GENERO IS NULL)'
                    parametros_cortes.extend(generos_servico)
                sql_cortes += ' ORDER BY NOME'
                cursor.execute(sql_cortes, parametros_cortes)
                return [serializar_corte(linha) for linha in cursor.fetchall()]
            
            # Busca cortes na categoria principal
            cortes = buscar_cortes(categorias)
            
            # Fallback: se não há cortes na categoria específica, tenta categoria 'cabelo'
            if not cortes and categoria != 'cabelo':
                categoria = 'cabelo'
                cortes = buscar_cortes(('cabelo',))
            
            if not cortes: return resposta_erro('Não há cortes cadastrados para este serviço.', 404)
            data_hora = datetime.now().strftime('%Y%m%d_%H%M%S')
            foto_nome, foto_caminho = salvar_arquivo(request.files.get('imagem'), app.config['VISAGISMO_FOTOS_FOLDER'],
                                                     f"cliente_{usuario['id_usuario']}_{data_hora}")
            try:
                analise_ia = analisar_com_ia(foto_caminho, cortes, categoria)
            except RuntimeError as erro_ia:
                # Sem chave/lib no servidor: salva a foto e devolve o catálogo
                # para o fluxo não travar. Com chave presente mas inválida,
                # retorna 502 com a causa real (401, modelo, quota).
                if motivo_sem_ia():
                    analise_ia = None
                else:
                    con.rollback()
                    return resposta_erro(str(erro_ia), 502)
            recomendadas = []
            if analise_ia:
                por_id = {corte['id_corte']: corte for corte in cortes}
                for item in analise_ia.get('recomendacoes', []):
                    corte = por_id.get(item.get('id_corte'))
                    if corte and corte['id_corte'] not in {c['id_corte'] for c in recomendadas}:
                        recomendadas.append({**corte,
                                             'motivo': str(item.get('motivo', 'Compatível com o serviço escolhido.')),
                                             'compativel_com_cabelo_existente': bool(item.get('compativel_com_cabelo_existente', True))})
                    if len(recomendadas) == 3: break
            if not recomendadas:
                recomendadas = [{**corte, 'motivo': 'Opção disponível para o serviço escolhido.'} for corte in cortes[:3]]
            analise = {'observacoes': (analise_ia or {}).get('observacoes', 'Selecione a opção que mais combina com você.'),
                       'cabelo_atual': (analise_ia or {}).get('cabelo_atual', ''),
                       'categoria': categoria, 'recomendacoes': recomendadas}
            cursor.execute('''INSERT INTO VISAGISMO_SESSAO
                              (ID_VISAGISMO, ID_USUARIO, ID_BARBEARIA, SERVICOS_JSON, FOTO_ROTA, ANALISE_JSON)
                              VALUES (NEXT VALUE FOR SEQ_VISAGISMO_SESSAO, ?, ?, ?, ?, ?)
                              RETURNING ID_VISAGISMO''', (usuario['id_usuario'], id_barbearia,
                                                             json.dumps(ids_servicos), foto_nome, json.dumps(analise, ensure_ascii=False)))
            id_visagismo = cursor.fetchone()[0]
            con.commit()
            return jsonify({'mensagem': {'informacao': 'Análise de visagismo concluída.', 'tipo': 'sucesso'},
                            'id_visagismo': id_visagismo, 'foto_url': f'/uploads/visagismo/fotos/{foto_nome}', **analise})
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Não foi possível analisar a foto: {erro}', 500)


@app.route('/visagismo/salvar-foto', methods=['POST'])
def salvar_foto_visagismo():
    """Salva a foto do cliente para uso posterior (simulação de cor) sem fazer análise de visagismo."""
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para usar o visagismo.', 401)
    try:
        garantir_estrutura(); garantir_pastas()
        id_barbearia = request.form.get('id_barbearia', type=int)
        ids_servicos = ids_servicos_da_requisicao(request.form)
        if not id_barbearia or not ids_servicos: return resposta_erro('Escolha a barbearia e ao menos um serviço.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            servicos = carregar_servicos(cursor, id_barbearia, ids_servicos)
            if not servicos: return resposta_erro('Serviços inválidos para a barbearia.', 400)
            data_hora = datetime.now().strftime('%Y%m%d_%H%M%S')
            foto_nome, foto_caminho = salvar_arquivo(request.files.get('imagem'), app.config['VISAGISMO_FOTOS_FOLDER'],
                                                     f"cliente_{usuario['id_usuario']}_{data_hora}")
            cursor.execute('''INSERT INTO VISAGISMO_SESSAO
                              (ID_VISAGISMO, ID_USUARIO, ID_BARBEARIA, SERVICOS_JSON, FOTO_ROTA, ANALISE_JSON)
                              VALUES (NEXT VALUE FOR SEQ_VISAGISMO_SESSAO, ?, ?, ?, ?, ?)
                              RETURNING ID_VISAGISMO''', 
                           (usuario['id_usuario'], id_barbearia,
                            json.dumps(ids_servicos), foto_nome, json.dumps({'categoria': 'pintura', 'apenas_cor': True}, ensure_ascii=False)))
            id_visagismo = cursor.fetchone()[0]
            con.commit()
            return jsonify({'mensagem': {'informacao': 'Foto salva com sucesso.', 'tipo': 'sucesso'},
                            'id_visagismo': id_visagismo, 'foto_url': f'/uploads/visagismo/fotos/{foto_nome}'})
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Não foi possível salvar a foto: {erro}', 500)


@app.route('/visagismo/<int:id_visagismo>/simular', methods=['POST'])
def simular_visagismo(id_visagismo):
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para gerar a simulação.', 401)
    try:
        garantir_estrutura(); garantir_pastas()
        dados_requisicao = request.get_json(silent=True) or {}
        id_corte = dados_requisicao.get('id_corte')
        cor = dados_requisicao.get('cor')
        # Alvo da coloração: 'cabelo', 'barba' ou 'ambos' (conforme o serviço escolhido).
        alvo = str(dados_requisicao.get('alvo', 'ambos') or 'ambos').strip().lower()
        if alvo not in ('cabelo', 'barba', 'ambos'):
            alvo = 'ambos'
        # Para "só pintar cabelo", id_corte pode ser opcional se tiver cor
        if not id_corte and not cor:
            return resposta_erro('Selecione um corte ou uma cor.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            cursor.execute('SELECT FOTO_ROTA, ANALISE_JSON FROM VISAGISMO_SESSAO WHERE ID_VISAGISMO=? AND ID_USUARIO=?',
                           (id_visagismo, usuario['id_usuario']))
            sessao = cursor.fetchone()
            if not sessao: return resposta_erro('Análise de visagismo não encontrada.', 404)
            
            # Se tem id_corte, busca info do corte
            nome_corte = ''
            descricao_corte = ''
            if id_corte:
                cursor.execute('SELECT NOME, DESCRICAO FROM CORTE_VISAGISMO WHERE ID_CORTE=? AND ATIVO=1', (id_corte,))
                corte = cursor.fetchone()
                if not corte: return resposta_erro('Corte não encontrado.', 404)
                nome_corte = corte[0]
                descricao_corte = corte[1] or ''
            
            if OpenAI is None:
                return resposta_erro('Biblioteca openai não instalada no servidor. Rode: pip install -r requirements.txt', 503)
            chave = (app.config.get('OPENAI_API_KEY') or '').strip()
            if not chave:
                return resposta_erro('A simulação requer OPENAI_API_KEY configurada no servidor (Backend/.env).', 503)
            caminho = os.path.join(app.config['VISAGISMO_FOTOS_FOLDER'], sessao[0])
            categoria = json_seguro(sessao[1]).get('categoria', 'cabelo')
            regra_barba = ('You may adjust only facial hair that visibly exists, as part of the selected beard service.'
                           if categoria == 'barba_cabelo' else
                           'Do NOT change facial hair. Do NOT add a beard. Do NOT add a moustache. '
                           'Do NOT remove existing beard or moustache.')
            # A cor só tinge o que o serviço contratado cobre.
            if cor and alvo == 'cabelo':
                instrucao_cor = (f"CHANGE HAIR COLOR: Change ONLY the scalp/head hair color to {cor}. "
                                 "Apply the color naturally to the head hair, keeping the same hairstyle and hair texture. "
                                 "Do NOT change the beard, moustache or eyebrow color.")
            elif cor and alvo == 'barba':
                instrucao_cor = (f"CHANGE BEARD COLOR: Change ONLY the facial hair (beard/moustache) color to {cor}. "
                                 "Apply the color naturally, keeping the same beard style and texture. "
                                 "Do NOT change the scalp/head hair color. Do NOT change the eyebrows.")
            elif cor:
                instrucao_cor = (f"CHANGE HAIR COLOR: Change the hair color to {cor}. "
                                 "Apply the color naturally to all visible hair, keeping the same hairstyle and hair texture.")
            else:
                instrucao_cor = ''
            
            if id_corte:
                prompt = f'''Edit ONLY the existing hairstyle in this photograph.
Selected hairstyle: {nome_corte}
Description: {descricao_corte}
{instrucao_cor}
STRICT REQUIREMENTS:
- Keep the exact same person.
- Preserve facial identity.
- Preserve facial structure.
- Preserve eyes.
- Preserve nose.
- Preserve mouth.
- Preserve ears.
- Preserve skin.
- Preserve expression.
- Preserve pose.
- Preserve camera angle.
- Preserve clothing.
- Preserve background.
- Preserve lighting.
- Preserve image composition.
HAIR RULES:
- Only modify hair that visibly exists in the original image.
- Do NOT create hair on an area where the person has no visible hair.
- Do NOT increase the person's original hair density.
- Do NOT create artificial hair volume.
- Do NOT create new hairline.
- Do NOT lower or raise the natural hairline.
- Do NOT extend hair into previously empty areas.
- Do NOT make the hair substantially longer than the original hair.
- Do NOT invent hair behind the head.
- Do NOT invent side hair.
- Do NOT invent bangs if there is insufficient existing hair.
- {regra_barba}
- Do NOT alter the face to accommodate the hairstyle.
The result must look like the same person receiving the selected haircut using only the hair that already exists.
The haircut should be realistic and recognizable, but must respect the original hair quantity, hairline, length and visible coverage.
Do not change anything unrelated to the hairstyle.'''
            else:
                # Apenas mudança de cor, sem mudança de corte
                prompt = f'''Edit ONLY the hair color in this photograph.
{instrucao_cor}
STRICT REQUIREMENTS:
- Keep the exact same person.
- Preserve facial identity.
- Preserve facial structure.
- Preserve eyes.
- Preserve nose.
- Preserve mouth.
- Preserve ears.
- Preserve skin.
- Preserve expression.
- Preserve pose.
- Preserve camera angle.
- Preserve clothing.
- Preserve background.
- Preserve lighting.
- Preserve image composition.
- Do NOT change the hairstyle, cut, or style.
- Only change the hair color.
'''
            with open(caminho, 'rb') as imagem:
                try:
                    resposta = OpenAI(api_key=chave).images.edit(
                        model=app.config['VISAGISMO_IMAGE_MODEL'], image=imagem, prompt=prompt, size='1024x1024', quality='low')
                except Exception as erro:
                    return resposta_erro(traduzir_erro_openai(erro), 502)
            dados_imagem = base64.b64decode(resposta.data[0].b64_json)
            nome = f"resultado_{usuario['id_usuario']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.png"
            with open(os.path.join(app.config['VISAGISMO_RESULTADOS_FOLDER'], nome), 'wb') as arquivo: arquivo.write(dados_imagem)
            cursor.execute('UPDATE VISAGISMO_SESSAO SET ID_CORTE_SIMULADO = ?, RESULTADO_ROTA = ? WHERE ID_VISAGISMO = ?',
                           (id_corte, nome, id_visagismo))
            con.commit()
            return jsonify({'mensagem': {'informacao': 'Simulação gerada.', 'tipo': 'sucesso'},
                            'imagem_url': f'/uploads/visagismo/resultados/{nome}'})
        finally:
            cursor.close(); con.close()
    except Exception as erro:
        return resposta_erro(f'Não foi possível gerar a simulação: {erro}', 500)


def parse_data(texto):
    try: return datetime.strptime(str(texto), '%Y-%m-%d').date()
    except ValueError: raise ValueError('Data inválida. Use AAAA-MM-DD.')


def intervalos_do_dia(cursor, id_barbearia, dia):
    cursor.execute('''SELECT ENTRADA_MANHA, SAIDA_MANHA, ENTRADA_TARDE, SAIDA_TARDE
                      FROM DIAS_DE_SERVICO WHERE ID_USUARIO=? AND DIAS=?''',
                   (id_barbearia, DIAS_SEMANA[dia.weekday()]))
    linha = cursor.fetchone()
    if not linha: return []
    resultado = []
    for inicio, fim in ((linha[0], linha[1]), (linha[2], linha[3])):
        if inicio and fim:
            resultado.append((datetime.combine(dia, inicio), datetime.combine(dia, fim)))
    return resultado


def buscar_funcionario(cursor, id_barbearia, id_funcionario):
    """Valida que o profissional pertence à barbearia (via dias vinculados)."""
    cursor.execute('''SELECT DISTINCT F.ID_FUNCIONARIO, F.NOME, F.DESCRICAO
                      FROM FUNCIONARIO F
                      INNER JOIN FUNCIONARIO_DIA FD ON FD.ID_FUNCIONARIO = F.ID_FUNCIONARIO
                      INNER JOIN DIAS_DE_SERVICO D ON D.ID_DIA = FD.ID_DIA
                      WHERE D.ID_USUARIO = ? AND F.ID_FUNCIONARIO = ?''',
                   (id_barbearia, id_funcionario))
    linha = cursor.fetchone()
    if not linha:
        return None
    return {'id_funcionario': linha[0], 'nome': linha[1], 'descricao': linha[2]}


def servicos_do_funcionario(cursor, id_barbearia, id_funcionario):
    cursor.execute('''SELECT SPF.ID_SERVICO
                      FROM SERVICO_POR_FUNCIONARIO SPF
                      INNER JOIN SERVICO S ON S.ID_SERVICO = SPF.ID_SERVICO
                      WHERE SPF.ID_FUNCIONARIO = ? AND S.ID_USUARIO = ?''',
                   (id_funcionario, id_barbearia))
    return {linha[0] for linha in cursor.fetchall()}


def dias_semana_do_funcionario(cursor, id_funcionario):
    cursor.execute('''SELECT DISTINCT D.DIAS
                      FROM FUNCIONARIO_DIA FD
                      INNER JOIN DIAS_DE_SERVICO D ON D.ID_DIA = FD.ID_DIA
                      WHERE FD.ID_FUNCIONARIO = ?''', (id_funcionario,))
    return {str(linha[0]).strip().lower() for linha in cursor.fetchall() if linha[0]}


def horarios_disponiveis(cursor, id_barbearia, dia, duracao_minutos, id_funcionario=None):
    if duracao_minutos <= 0: return []
    # Com barbeiro escolhido, a ocupação é só a agenda dele; sem escolha, a da barbearia toda.
    # Agendamentos concluídos ou cancelados não bloqueiam novos horários.
    if id_funcionario:
        cursor.execute('''SELECT INICIO_EM, FIM_EM FROM AGENDAMENTO
                          WHERE ID_FUNCIONARIO=? AND STATUS IN ('agendado', 'confirmado')
                            AND INICIO_EM < ? AND FIM_EM > ?''',
                       (id_funcionario, datetime.combine(dia + timedelta(days=1), time.min), datetime.combine(dia, time.min)))
    else:
        cursor.execute('''SELECT INICIO_EM, FIM_EM FROM AGENDAMENTO
                          WHERE ID_BARBEARIA=? AND STATUS IN ('agendado', 'confirmado')
                            AND INICIO_EM < ? AND FIM_EM > ?''',
                       (id_barbearia, datetime.combine(dia + timedelta(days=1), time.min), datetime.combine(dia, time.min)))
    ocupados = cursor.fetchall(); agora = datetime.now(); disponiveis = []
    intervalos = intervalos_do_dia(cursor, id_barbearia, dia)
    if id_funcionario:
        dias_func = dias_semana_do_funcionario(cursor, id_funcionario)
        if DIAS_SEMANA[dia.weekday()] not in dias_func:
            return []
    # O passo acompanha a duração total dos serviços escolhidos, por isso
    # horários quebrados (ex.: 08:40 para um serviço de 40 min) aparecem.
    passo = max(5, int(duracao_minutos))
    for inicio_turno, fim_turno in intervalos:
        candidato = inicio_turno
        while candidato + timedelta(minutes=duracao_minutos) <= fim_turno:
            fim = candidato + timedelta(minutes=duracao_minutos)
            livre = candidato >= agora and not any(candidato < fim_ocupado and fim > inicio_ocupado for inicio_ocupado, fim_ocupado in ocupados)
            disponiveis.append({'horario': candidato.strftime('%H:%M'), 'fim': fim.strftime('%H:%M'), 'disponivel': livre})
            candidato += timedelta(minutes=passo)
    return disponiveis


@app.route('/agendamentos/horarios', methods=['GET'])
def listar_horarios_agendamento():
    try:
        garantir_estrutura()
        id_barbearia = request.args.get('id_barbearia', type=int); ids = ids_servicos_da_requisicao(request.args)
        dia = parse_data(request.args.get('data'))
        id_funcionario = request.args.get('id_funcionario', type=int)
        if not id_barbearia or not ids: return resposta_erro('Informe barbearia e serviços.')
        if dia < date.today(): return resposta_erro('Não é possível agendar em data anterior à atual.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            servicos = carregar_servicos(cursor, id_barbearia, ids)
            if not servicos: return resposta_erro('Serviços inválidos para esta barbearia.', 400)
            funcionario = None
            if id_funcionario:
                funcionario = buscar_funcionario(cursor, id_barbearia, id_funcionario)
                if not funcionario: return resposta_erro('Profissional não encontrado nesta barbearia.', 404)
                if not set(ids) <= servicos_do_funcionario(cursor, id_barbearia, id_funcionario):
                    return resposta_erro('Este profissional não atende todos os serviços escolhidos.', 400)
            duracao = sum(servico['duracao'] for servico in servicos)
            return jsonify({'mensagem': {'informacao': 'Horários consultados.', 'tipo': 'sucesso'},
                            'data': dia.isoformat(), 'duracao_minutos': duracao,
                            'funcionario': funcionario,
                            'horarios': horarios_disponiveis(cursor, id_barbearia, dia, duracao, id_funcionario)})
        finally:
            cursor.close(); con.close()
    except ValueError as erro: return resposta_erro(str(erro))
    except Exception as erro: return resposta_erro(f'Erro ao consultar horários: {erro}', 500)


@app.route('/agendamentos', methods=['POST'])
def criar_agendamento():
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para agendar.', 401)
    try:
        garantir_estrutura()
        dados = request.get_json(silent=True) or {}
        id_barbearia = dados.get('id_barbearia'); ids = ids_servicos_da_requisicao(dados)
        try: id_funcionario = int(dados.get('id_funcionario')) if dados.get('id_funcionario') not in (None, '') else None
        except (TypeError, ValueError): return resposta_erro('Profissional inválido.')
        dia = parse_data(dados.get('data')); horario = str(dados.get('horario', ''))
        try: inicio = datetime.combine(dia, datetime.strptime(horario, '%H:%M').time())
        except ValueError: return resposta_erro('Horário inválido.')
        if dia < date.today() or inicio < datetime.now(): return resposta_erro('Não é possível agendar no passado.')
        if not id_barbearia or not ids: return resposta_erro('Informe barbearia e serviços.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            servicos = carregar_servicos(cursor, int(id_barbearia), ids)
            if not servicos: return resposta_erro('Serviços inválidos para a barbearia.', 400)
            funcionario = None
            if id_funcionario:
                funcionario = buscar_funcionario(cursor, int(id_barbearia), id_funcionario)
                if not funcionario: return resposta_erro('Profissional não encontrado nesta barbearia.', 404)
                if not set(ids) <= servicos_do_funcionario(cursor, int(id_barbearia), id_funcionario):
                    return resposta_erro('Este profissional não atende todos os serviços escolhidos.', 400)
            fim = inicio + timedelta(minutes=sum(servico['duracao'] for servico in servicos))
            if not any(inicio >= a and fim <= b for a, b in intervalos_do_dia(cursor, int(id_barbearia), dia)):
                return resposta_erro('O horário está fora do expediente ou não comporta todos os serviços.')
            # Trava a barbearia durante a validação. Isso serializa tentativas
            # concorrentes inclusive quando ainda não existe agendamento no dia.
            cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (int(id_barbearia),))
            if not cursor.fetchone(): return resposta_erro('Barbearia não encontrada.', 404)
            # O lock + verificação no mesmo commit impede duas reservas simultâneas no mesmo intervalo.
            # Agendamentos ativos bloqueiam o horário; apenas os cancelados e
            # finalizados o liberam.
            if id_funcionario:
                cursor.execute('''SELECT ID_AGENDAMENTO FROM AGENDAMENTO
                                  WHERE ID_FUNCIONARIO=? AND STATUS IN ('agendado', 'confirmado') AND INICIO_EM < ? AND FIM_EM > ?
                                      WITH LOCK''', (id_funcionario, fim, inicio))
            else:
                cursor.execute('''SELECT ID_AGENDAMENTO FROM AGENDAMENTO
                                  WHERE ID_BARBEARIA=? AND STATUS IN ('agendado', 'confirmado') AND INICIO_EM < ? AND FIM_EM > ?
                                      WITH LOCK''', (int(id_barbearia), fim, inicio))
            if cursor.fetchone(): return resposta_erro('Este horário acabou de ser reservado. Escolha outro.', 409)
            cursor.execute('''INSERT INTO AGENDAMENTO
                              (ID_AGENDAMENTO, ID_USUARIO, ID_BARBEARIA, ID_FUNCIONARIO, INICIO_EM, FIM_EM, SERVICOS_JSON, ID_CORTE, ID_VISAGISMO, STATUS)
                              VALUES (NEXT VALUE FOR SEQ_AGENDAMENTO, ?, ?, ?, ?, ?, ?, ?, ?, 'agendado')
                              RETURNING ID_AGENDAMENTO''',
                           (usuario['id_usuario'], int(id_barbearia), id_funcionario, inicio, fim, json.dumps(ids),
                            dados.get('id_corte'), dados.get('id_visagismo')))
            id_agendamento = cursor.fetchone()[0]
            marcadores = ','.join('?' for _ in ids)
            cursor.execute(f'SELECT PRECO FROM SERVICO WHERE ID_USUARIO = ? AND ID_SERVICO IN ({marcadores})',
                           [int(id_barbearia), *ids])
            valor_total = round(float(sum(float(l[0] or 0) for l in cursor.fetchall())), 2)
            con.commit()
            return jsonify({'mensagem': {'informacao': 'Agendamento realizado!', 'tipo': 'sucesso'},
                            'agendamento': {'id_agendamento': id_agendamento, 'inicio_em': inicio.isoformat(), 'fim_em': fim.isoformat(),
                                            'id_funcionario': id_funcionario, 'valor_total': valor_total,
                                            'status': 'agendado'}}), 201
        finally:
            cursor.close(); con.close()
    except ValueError as erro: return resposta_erro(str(erro))
    except Exception as erro: return resposta_erro(f'Não foi possível criar o agendamento: {erro}', 500)


COLUNAS_AGENDAMENTO = ('ID_AGENDAMENTO, ID_USUARIO, ID_BARBEARIA, ID_FUNCIONARIO, INICIO_EM, '
                       'FIM_EM, SERVICOS_JSON, ID_CORTE, ID_VISAGISMO, STATUS, CRIADO_EM')


def email_do_cliente(cursor, id_usuario):
    cursor.execute('SELECT NOME, EMAIL FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
    linha = cursor.fetchone()
    return {'nome': linha[0], 'email': linha[1]} if linha else {'nome': '', 'email': ''}


def email_da_barbearia(cursor, id_barbearia):
    cursor.execute('SELECT NOME, EMAIL FROM USUARIO WHERE ID_USUARIO = ?', (id_barbearia,))
    usuario = cursor.fetchone()
    cursor.execute('SELECT CONTATO_EMAIL FROM PERSONALIZACAO WHERE ID_USUARIO = ?', (id_barbearia,))
    contato = cursor.fetchone()
    email = (contato[0] if contato and contato[0] else (usuario[1] if usuario else ''))
    return {'nome': usuario[0] if usuario else 'Barbearia', 'email': (email or '').strip()}


def serializar_agendamento(cursor, linha):
    ag = {'id_agendamento': linha[0], 'id_usuario': linha[1], 'id_barbearia': linha[2],
          'id_funcionario': linha[3], 'inicio_em': linha[4].isoformat(), 'fim_em': linha[5].isoformat(),
          'servicos': json_seguro(linha[6], []), 'id_corte': linha[7], 'id_visagismo': linha[8],
          'status': linha[9]}
    cliente = email_do_cliente(cursor, linha[1])
    barbearia = email_da_barbearia(cursor, linha[2])
    ag['cliente_nome'] = cliente['nome']
    ag['barbearia_nome'] = barbearia['nome']
    if linha[3]:
        cursor.execute('SELECT NOME FROM FUNCIONARIO WHERE ID_FUNCIONARIO = ?', (linha[3],))
        func = cursor.fetchone()
        ag['funcionario_nome'] = func[0] if func else None
    if ag['servicos']:
        marcadores = ','.join('?' for _ in ag['servicos'])
        cursor.execute(f'SELECT NOME_SERVICO FROM SERVICO WHERE ID_SERVICO IN ({marcadores})', list(ag['servicos']))
        ag['servicos_nomes'] = [l[0] for l in cursor.fetchall()]
        cursor.execute(f'SELECT PRECO FROM SERVICO WHERE ID_SERVICO IN ({marcadores})', list(ag['servicos']))
        ag['valor_total'] = round(float(sum(float(l[0] or 0) for l in cursor.fetchall())), 2)
    else:
        ag['valor_total'] = 0.0
    if linha[7]:
        cursor.execute('SELECT NOME, IMAGEM_ROTA FROM CORTE_VISAGISMO WHERE ID_CORTE = ?', (linha[7],))
        corte = cursor.fetchone()
        ag['corte_nome'] = corte[0] if corte else None
        ag['corte_imagem_url'] = f'/uploads/visagismo/cortes/{corte[1]}' if corte and corte[1] else None
    if linha[8]:
        cursor.execute('SELECT FOTO_ROTA, RESULTADO_ROTA FROM VISAGISMO_SESSAO WHERE ID_VISAGISMO = ?', (linha[8],))
        sessao = cursor.fetchone()
        ag['visagismo_foto_url'] = f'/uploads/visagismo/fotos/{sessao[0]}' if sessao and sessao[0] else None
        # A foto do corte é a simulação gerada por IA; sem simulação, usa a referência do catálogo.
        if sessao and sessao[1]:
            ag['corte_imagem_url'] = f'/uploads/visagismo/resultados/{sessao[1]}'
    cursor.execute('''SELECT H.ID_HISTORICO, H.STATUS, H.REGISTRADO_EM, U.NOME
                      FROM AGENDAMENTO_HISTORICO H
                      LEFT JOIN USUARIO U ON U.ID_USUARIO = H.ID_USUARIO_RESPONSAVEL
                      WHERE H.ID_AGENDAMENTO = ?
                      ORDER BY H.REGISTRADO_EM DESC, H.ID_HISTORICO DESC''', (linha[0],))
    ag['historico_atendimento'] = [
        {
            'id_historico': historico[0],
            'status': historico[1],
            'registrado_em': historico[2].isoformat() if historico[2] else None,
            'responsavel_nome': historico[3] or 'Barbearia'
        }
        for historico in cursor.fetchall()
    ]
    return ag


def buscar_agendamento(cursor, id_agendamento):
    cursor.execute(f'SELECT {COLUNAS_AGENDAMENTO} FROM AGENDAMENTO WHERE ID_AGENDAMENTO = ?', (id_agendamento,))
    return cursor.fetchone()


def pode_ver_agendamento(usuario, linha, id_barbearia_alvo=None):
    tipo = int(usuario.get('tipo', -1))
    if tipo == 0:
        return True
    if tipo == 1:
        return int(linha[1]) == int(usuario['id_usuario'])
    return int(linha[2]) == int(id_barbearia_alvo or usuario['id_usuario'])


def notificar(destino, assunto, texto, remetente='Cortaê'):
    if not destino.get('email'):
        return False
    try:
        return bool(enviar_aviso_email(destino['email'], destino['nome'] or 'cliente', assunto, texto, remetente))
    except Exception:
        return False


@app.route('/agendamentos', methods=['GET'])
def listar_agendamentos():
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para ver agendamentos.', 401)
    try:
        garantir_estrutura()
        tipo = int(usuario.get('tipo', -1))
        status = request.args.get('status')
        data = request.args.get('data')
        con = conectar_banco(); cursor = con.cursor()
        try:
            sql = f'SELECT {COLUNAS_AGENDAMENTO} FROM AGENDAMENTO WHERE 1 = 1'
            params = []
            if tipo == 1:
                sql += ' AND ID_USUARIO = ?'
                params.append(usuario['id_usuario'])
            elif tipo == 2:
                alvo = pegar_id_barbearia_alvo() or usuario['id_usuario']
                sql += ' AND ID_BARBEARIA = ?'
                params.append(alvo)
            else:
                if request.args.get('id_barbearia', type=int):
                    sql += ' AND ID_BARBEARIA = ?'
                    params.append(request.args.get('id_barbearia', type=int))
                if request.args.get('id_usuario', type=int):
                    sql += ' AND ID_USUARIO = ?'
                    params.append(request.args.get('id_usuario', type=int))
            if status:
                sql += ' AND STATUS = ?'
                params.append(status)
            if data:
                sql += ' AND CAST(INICIO_EM AS DATE) = ?'
                params.append(parse_data(data))
            sql += ' ORDER BY INICIO_EM'
            cursor.execute(sql, params)
            return jsonify({'mensagem': {'informacao': 'Agendamentos listados.', 'tipo': 'sucesso'},
                            'agendamentos': [serializar_agendamento(cursor, linha) for linha in cursor.fetchall()]})
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Não foi possível listar agendamentos: {erro}', 500)


@app.route('/agendamentos/<int:id_agendamento>/cancelar', methods=['PUT'])
def cancelar_agendamento(id_agendamento):
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para cancelar.', 401)
    try:
        garantir_estrutura()
        con = conectar_banco(); cursor = con.cursor()
        try:
            linha = buscar_agendamento(cursor, id_agendamento)
            if not linha: return resposta_erro('Agendamento não encontrado.', 404)
            if not pode_ver_agendamento(usuario, linha, pegar_id_barbearia_alvo()):
                return resposta_erro('Sem permissão para cancelar este agendamento.', 403)
            if linha[9] in ('concluido', 'faltou'):
                return resposta_erro('Atendimento finalizado não pode ser cancelado.', 400)
            if linha[9] == 'cancelado':
                return jsonify({'mensagem': {'informacao': 'Agendamento já estava cancelado.', 'tipo': 'aviso'}})
            cursor.execute("UPDATE AGENDAMENTO SET STATUS = 'cancelado' WHERE ID_AGENDAMENTO = ?", (id_agendamento,))
            con.commit()
            tipo = int(usuario.get('tipo', -1))
            if tipo == 1:
                destino = email_da_barbearia(cursor, linha[2])
                remetente = email_do_cliente(cursor, linha[1])['nome']
            else:
                destino = email_do_cliente(cursor, linha[1])
                remetente = email_da_barbearia(cursor, linha[2])['nome']
            texto = (f"O agendamento #{id_agendamento} de {linha[4]} foi cancelado por {remetente}. "
                     f"Entre em contato para reagendar.")
            email_ok = notificar(destino, 'Agendamento cancelado', texto, remetente)
            return jsonify({'mensagem': {'informacao': 'Agendamento cancelado.' + ('' if email_ok else ' (e-mail não enviado)'),
                                         'tipo': 'sucesso'}, 'email_enviado': email_ok})
        finally:
            cursor.close(); con.close()
    except Exception as erro:
        return resposta_erro(f'Não foi possível cancelar: {erro}', 500)


@app.route('/agendamentos/<int:id_agendamento>/reagendar', methods=['PUT'])
def reagendar_agendamento(id_agendamento):
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para reagendar.', 401)
    try:
        garantir_estrutura()
        dados = request.get_json(silent=True) or {}
        dia = parse_data(dados.get('data')); horario = str(dados.get('horario', ''))
        try: inicio = datetime.combine(dia, datetime.strptime(horario, '%H:%M').time())
        except ValueError: return resposta_erro('Horário inválido.')
        if dia < date.today() or inicio < datetime.now(): return resposta_erro('Não é possível agendar no passado.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            linha = buscar_agendamento(cursor, id_agendamento)
            if not linha: return resposta_erro('Agendamento não encontrado.', 404)
            if not pode_ver_agendamento(usuario, linha, pegar_id_barbearia_alvo()):
                return resposta_erro('Sem permissão para reagendar.', 403)
            if linha[9] in ('concluido', 'faltou'):
                return resposta_erro('Atendimento finalizado não pode ser reagendado.', 400)
            if linha[9] == 'cancelado': return resposta_erro('Agendamento cancelado não pode ser reagendado.')
            ids = json_seguro(linha[6], [])
            servicos = carregar_servicos(cursor, linha[2], ids)
            if not servicos: return resposta_erro('Serviços do agendamento inválidos.', 400)
            try: id_func = int(dados.get('id_funcionario')) if dados.get('id_funcionario') not in (None, '') else linha[3]
            except (TypeError, ValueError): return resposta_erro('Profissional inválido.')
            if id_func and (not buscar_funcionario(cursor, linha[2], id_func)
                            or not set(ids) <= servicos_do_funcionario(cursor, linha[2], id_func)):
                return resposta_erro('Profissional inválido para estes serviços.', 400)
            fim = inicio + timedelta(minutes=sum(s['duracao'] for s in servicos))
            if not any(inicio >= a and fim <= b for a, b in intervalos_do_dia(cursor, linha[2], dia)):
                return resposta_erro('O horário está fora do expediente ou não comporta todos os serviços.')
            cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (linha[2],))
            if id_func:
                cursor.execute('''SELECT ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_FUNCIONARIO=?
                                  AND STATUS IN ('agendado', 'confirmado') AND INICIO_EM < ? AND FIM_EM > ?
                                  AND ID_AGENDAMENTO <> ? WITH LOCK''', (id_func, fim, inicio, id_agendamento))
            else:
                cursor.execute('''SELECT ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_BARBEARIA=?
                                  AND STATUS IN ('agendado', 'confirmado') AND INICIO_EM < ? AND FIM_EM > ?
                                  AND ID_AGENDAMENTO <> ? WITH LOCK''', (linha[2], fim, inicio, id_agendamento))
            if cursor.fetchone(): return resposta_erro('Este horário está ocupado. Escolha outro.', 409)
            cursor.execute('''UPDATE AGENDAMENTO SET INICIO_EM=?, FIM_EM=?, ID_FUNCIONARIO=?, STATUS='agendado'
                              WHERE ID_AGENDAMENTO=?''', (inicio, fim, id_func, id_agendamento))
            con.commit()
            tipo = int(usuario.get('tipo', -1))
            if tipo == 1:
                destino = email_da_barbearia(cursor, linha[2])
                remetente = email_do_cliente(cursor, linha[1])['nome']
            else:
                destino = email_do_cliente(cursor, linha[1])
                remetente = email_da_barbearia(cursor, linha[2])['nome']
            texto = (f"O agendamento #{id_agendamento} foi reagendado por {remetente} para "
                     f"{inicio.strftime('%d/%m/%Y às %H:%M')}.")
            email_ok = notificar(destino, 'Agendamento reagendado', texto, remetente)
            return jsonify({'mensagem': {'informacao': 'Agendamento reagendado.' + ('' if email_ok else ' (e-mail não enviado)'),
                                         'tipo': 'sucesso'}, 'email_enviado': email_ok,
                            'agendamento': {'id_agendamento': id_agendamento, 'inicio_em': inicio.isoformat(),
                                            'fim_em': fim.isoformat()}})
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Não foi possível reagendar: {erro}', 500)


@app.route('/agendamentos/<int:id_agendamento>/status-atendimento', methods=['PUT'])
def registrar_status_atendimento(id_agendamento):
    """Registra manualmente se o cliente foi atendido ou não compareceu."""
    usuario = obter_usuario_logado()
    if not usuario:
        return resposta_erro('Faça login para registrar o atendimento.', 401)
    if int(usuario.get('tipo', -1)) not in (0, 2):
        return resposta_erro('Apenas a barbearia pode registrar o atendimento.', 403)

    dados = request.get_json(silent=True) or {}
    status = str(dados.get('status', '')).strip().lower()
    if status not in ('concluido', 'faltou'):
        return resposta_erro("Informe o status 'concluido' ou 'faltou'.")

    try:
        garantir_estrutura()
        con = conectar_banco(); cursor = con.cursor()
        try:
            linha = buscar_agendamento(cursor, id_agendamento)
            if not linha:
                return resposta_erro('Agendamento não encontrado.', 404)
            if not pode_ver_agendamento(usuario, linha, pegar_id_barbearia_alvo()):
                return resposta_erro('Sem permissão para registrar este atendimento.', 403)
            if linha[9] not in ('agendado', 'confirmado'):
                return resposta_erro('Este agendamento já foi finalizado ou cancelado.', 400)
            if linha[5] > datetime.now():
                return resposta_erro('O atendimento só pode ser registrado após o horário agendado.', 400)

            cursor.execute('UPDATE AGENDAMENTO SET STATUS = ? WHERE ID_AGENDAMENTO = ?',
                           (status, id_agendamento))
            cursor.execute('''INSERT INTO AGENDAMENTO_HISTORICO
                              (ID_HISTORICO, ID_AGENDAMENTO, STATUS, ID_USUARIO_RESPONSAVEL)
                              VALUES (NEXT VALUE FOR SEQ_AGENDAMENTO_HISTORICO, ?, ?, ?)''',
                           (id_agendamento, status, usuario['id_usuario']))
            con.commit()
            descricao = 'Atendimento concluído.' if status == 'concluido' else 'Falta do cliente registrada.'
            return jsonify({'mensagem': {'informacao': descricao, 'tipo': 'sucesso'},
                            'agendamento': {'id_agendamento': id_agendamento, 'status': status}})
        finally:
            cursor.close(); con.close()
    except Exception as erro:
        return resposta_erro(f'Não foi possível registrar o atendimento: {erro}', 500)


@app.route('/agendamentos/<int:id_agendamento>/avisar', methods=['POST'])
def avisar_cliente(id_agendamento):
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para enviar avisos.', 401)
    if int(usuario.get('tipo', -1)) not in (0, 2):
        return resposta_erro('Apenas a barbearia pode enviar avisos.', 403)
    try:
        garantir_estrutura()
        texto = str((request.get_json(silent=True) or {}).get('texto', '')).strip()
        if not texto: return resposta_erro('Escreva o texto do aviso.')
        if len(texto) > 500: return resposta_erro('O aviso deve ter até 500 caracteres.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            linha = buscar_agendamento(cursor, id_agendamento)
            if not linha: return resposta_erro('Agendamento não encontrado.', 404)
            if not pode_ver_agendamento(usuario, linha, pegar_id_barbearia_alvo()):
                return resposta_erro('Sem permissão para avisar este cliente.', 403)
            cursor.execute('INSERT INTO AVISO (ID_AVISO, ID_USUARIO, TEXTO, DATA_POSTAGEM) VALUES (NEXT VALUE FOR SEQ_AVISO, ?, ?, CURRENT_TIMESTAMP)',
                           (linha[1], texto))
            con.commit()
            cliente = email_do_cliente(cursor, linha[1])
            barbearia = email_da_barbearia(cursor, linha[2])
            email_ok = notificar(cliente, f"Aviso da {barbearia['nome']} (agendamento #{id_agendamento})",
                                 texto, barbearia['nome'])
            return jsonify({'mensagem': {'informacao': 'Aviso enviado.' + ('' if email_ok else ' (e-mail não enviado)'),
                                         'tipo': 'sucesso'}, 'email_enviado': email_ok}), 201
        finally:
            cursor.close(); con.close()
    except Exception as erro:
        return resposta_erro(f'Não foi possível enviar o aviso: {erro}', 500)


@app.route('/uploads/visagismo/<tipo>/<path:nome>', methods=['GET'])
def servir_upload_visagismo(tipo, nome):
    pastas = {'cortes': app.config['VISAGISMO_CORTES_FOLDER'], 'fotos': app.config['VISAGISMO_FOTOS_FOLDER'],
              'resultados': app.config['VISAGISMO_RESULTADOS_FOLDER']}
    if tipo not in pastas: return resposta_erro('Arquivo não encontrado.', 404)
    # Referências de cortes são públicas; fotos e simulações pertencem ao cliente,
    # mas a barbearia dona da sessão de visagismo também pode ver a foto original.
    if tipo in {'fotos', 'resultados'}:
        usuario = obter_usuario_logado()
        if not usuario:
            return resposta_erro('Sem permissão para acessar esta imagem.', 403)
        tipo_usuario = int(usuario.get('tipo', -1))
        dono = re.match(r'^(?:cliente|resultado)_(\d+)_', nome)
        e_dono = bool(dono) and int(dono.group(1)) == int(usuario['id_usuario'])
        e_barbearia_da_sessao = False
        if tipo_usuario == 2 and tipo in {'fotos', 'resultados'}:
            con = conectar_banco(); cursor = con.cursor()
            try:
                if tipo == 'fotos':
                    cursor.execute('SELECT ID_BARBEARIA FROM VISAGISMO_SESSAO WHERE FOTO_ROTA = ?', (nome,))
                else:
                    cursor.execute('SELECT ID_BARBEARIA FROM VISAGISMO_SESSAO WHERE RESULTADO_ROTA = ?', (nome,))
                sessao = cursor.fetchone()
                e_barbearia_da_sessao = bool(sessao) and int(sessao[0]) == int(usuario['id_usuario'])
            finally:
                cursor.close(); con.close()
        if tipo_usuario != 0 and not e_dono and not e_barbearia_da_sessao:
            return resposta_erro('Sem permissão para acessar esta imagem.', 403)
    return send_from_directory(pastas[tipo], nome)
