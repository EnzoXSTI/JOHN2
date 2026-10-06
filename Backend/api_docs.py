"""Documentação OpenAPI mantida junto ao backend Flask.

Flask não cria documentação automática como o FastAPI. Este módulo fornece o
mesmo ponto de entrada de uso (`/docs`) e publica o contrato em `/openapi.json`
sem acrescentar uma dependência de produção apenas para a interface.
"""

from flask import jsonify, render_template_string

from main import app


# Respostas padronizadas tornam a especificação curta e deixam claro que toda
# mensagem de falha usa `mensagem.informacao` ou `erro` no corpo JSON.
RESPOSTAS_PADRAO = {
    '200': {'description': 'Operação concluída.'},
    '201': {'description': 'Recurso criado.'},
    '400': {'description': 'Dados inválidos ou incompletos.'},
    '401': {'description': 'Sessão ausente, expirada ou inválida.'},
    '403': {'description': 'Perfil sem permissão.'},
    '404': {'description': 'Recurso não encontrado.'},
    '409': {'description': 'Conflito de dados, como horário já reservado.'},
    '502': {'description': 'Falha em serviço externo.'},
    '503': {'description': 'Serviço temporariamente indisponível.'},
    '500': {'description': 'Erro interno do servidor.'},
}


def operacao(resumo, descricao, corpo=None, autenticada=True):
    """Evita repetir o bloco de autenticação em cada operação do contrato."""
    resultado = {
        'summary': resumo,
        'description': descricao,
        'responses': RESPOSTAS_PADRAO,
    }
    if corpo:
        resultado['requestBody'] = {
            'required': True,
            'content': {'application/json': {'schema': corpo}},
        }
    if autenticada:
        resultado['security'] = [{'cookieAuth': []}]
    return resultado


USUARIO = {
    'type': 'object',
    'required': ['nome', 'email', 'telefone', 'senha', 'confirmarSenha', 'tipo'],
    'properties': {
        'nome': {'type': 'string', 'example': 'Maria Silva'},
        'email': {'type': 'string', 'format': 'email', 'example': 'maria@email.com'},
        'telefone': {'type': 'string', 'example': '11999999999'},
        'senha': {'type': 'string', 'format': 'password'},
        'confirmarSenha': {'type': 'string', 'format': 'password'},
        'tipo': {'type': 'integer', 'enum': [0, 1, 2], 'description': '0 ADM, 1 cliente, 2 barbearia.'},
        'genero': {'type': 'string', 'enum': ['masculino', 'feminino', 'outro'], 'description': 'Opcional no cadastro e disponível somente para o perfil cliente.'},
    },
}


SERVICO = {
    'type': 'object',
    'required': ['nome', 'preco', 'duracao', 'genero'],
    'properties': {
        'nome': {'type': 'string', 'example': 'Corte degradê'},
        'preco': {'type': 'number', 'format': 'float', 'minimum': 0, 'example': 45.0},
        'duracao': {'type': 'integer', 'minimum': 1, 'description': 'Duração total do serviço em minutos.', 'example': 45},
        'genero': {'type': 'string', 'enum': ['masculino', 'feminino', 'unissex'], 'description': 'Público do serviço; define o catálogo de cortes exibido.'},
        'descricao': {'type': 'string', 'example': 'Acabamento com máquina e tesoura.'},
    },
}


PERFIL = {
    'type': 'object',
    'properties': {
        'nome': {'type': 'string', 'example': 'Maria Silva'},
        'email': {'type': 'string', 'format': 'email'},
        'telefone': {'type': 'string', 'example': '11999999999'},
        'senha': {'type': 'string', 'format': 'password', 'description': 'Opcional; mantenha vazio para não alterar.'},
        'genero': {'type': 'string', 'enum': ['masculino', 'feminino', 'outro'], 'description': 'Campo do perfil cliente; pode ficar vazio.'},
        'foto': {'type': 'string', 'format': 'binary'},
    },
}


# Campos da personalização são multipart porque também incluem logo e fotos.
# A tela /docs informa esse detalhe para que o teste manual não envie JSON.
PERSONALIZACAO = {
    'type': 'object',
    'properties': {
        'cor_primaria': {'type': 'string', 'example': '#121212'},
        'cor_secundaria': {'type': 'string', 'example': '#D57C15'},
        'cor_terciaria': {'type': 'string', 'example': '#FFFFFF'},
        'cor_texto_primario': {'type': 'string', 'example': '#FFFFFF'},
        'cor_texto_secundario': {'type': 'string', 'example': '#333333'},
        'texto': {'type': 'string'},
        'localizacao': {'type': 'string'},
        'contato_telefone': {'type': 'string'},
        'contato_email': {'type': 'string', 'format': 'email'},
        'instagram': {'type': 'string'},
        'chave_pix': {'type': 'string', 'description': 'Obrigatória para receber pagamentos.'},
        'arkhe_client_id': {'type': 'string', 'description': 'Client ID da conta Arkhé; obrigatório.'},
        'arkhe_client_secret': {'type': 'string', 'format': 'password', 'description': 'Client Secret da conta Arkhé; obrigatório.'},
        'logo': {'type': 'string', 'format': 'binary'},
        'fotos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'}},
        'funcionarios[0][nome]': {'type': 'string'},
        'funcionarios[0][dias]': {'type': 'string', 'example': 'segunda,terca'},
        'funcionarios[0][servicos]': {'type': 'string', 'example': '1,2'},
    },
}


# Corte do catálogo de visagismo. Criação/edição são multipart porque aceitam
# upload de imagem OU imagem_url HTTPS.
VISAGISMO_CORTE = {
    'type': 'object',
    'properties': {
        'nome': {'type': 'string', 'example': 'Low Fade'},
        'descricao': {'type': 'string', 'example': 'Degradê baixo com topo texturizado.'},
        'categoria': {'type': 'string', 'enum': ['cabelo', 'barba', 'barba_cabelo', 'corte_pintura', 'pintura']},
        'genero': {'type': 'string', 'enum': ['masculino', 'feminino', 'unissex'], 'description': 'Filtro do catálogo. A seleção depende do serviço escolhido, não do gênero do cliente.'},
        'imagem': {'type': 'string', 'format': 'binary', 'description': 'Arquivo JPG, PNG ou WEBP de até 10 MB.'},
        'imagem_url': {'type': 'string', 'format': 'uri', 'example': 'https://exemplo.com/corte.jpg'},
    },
}


AGENDAMENTO = {
    'type': 'object',
    'required': ['id_barbearia', 'ids_servicos', 'data', 'horario'],
    'properties': {
        'id_barbearia': {'type': 'integer', 'example': 3},
        'ids_servicos': {'type': 'array', 'items': {'type': 'integer'}, 'example': [1, 2]},
        'data': {'type': 'string', 'format': 'date', 'example': '2026-10-05'},
        'horario': {'type': 'string', 'example': '14:30'},
        'id_corte': {'type': 'integer', 'description': 'Opcional: corte escolhido no visagismo.'},
        'id_visagismo': {'type': 'integer', 'description': 'Opcional: sessão de visagismo que originou a escolha.'},
        'id_funcionario': {'type': 'integer', 'description': 'Opcional: barbeiro escolhido. Deve pertencer à barbearia e atender todos os serviços.'},
    },
}


OPENAPI = {
    'openapi': '3.0.3',
    'info': {
        'title': 'Cortaê API',
        'version': '1.2.0',
        'description': 'API do sistema Cortaê. O login grava o JWT no cookie `access_token`. Rotas autenticadas exigem o cookie; chamadas feitas pelo frontend usam `credentials: include`. Agendamentos iniciam como `agendado`; só cliente ou barbearia podem cancelá-los e, após o horário, a barbearia registra se o atendimento foi concluído ou se houve falta.',
    },
    'servers': [{'url': 'http://localhost:5000', 'description': 'Servidor local'}],
    'paths': {
        '/cadastro': {'post': operacao('Cadastrar usuário', 'Cria usuário e envia código de confirmação por e-mail.', USUARIO, False)},
        '/verificar-codigo': {'post': operacao('Confirmar e-mail', 'Ativa o cadastro usando o código de seis dígitos.', {
            'type': 'object', 'required': ['email', 'codigo'], 'properties': {'email': {'type': 'string'}, 'codigo': {'type': 'string', 'example': '123456'}}
        }, False)},
        '/login': {'post': operacao('Entrar', 'Autentica e grava o cookie de sessão.', {
            'type': 'object', 'required': ['email', 'senha'], 'properties': {'email': {'type': 'string'}, 'senha': {'type': 'string', 'format': 'password'}}
        }, False)},
        '/logout': {'post': operacao('Sair', 'Remove o cookie de sessão.')},
        '/recuperar-senha': {'post': operacao('Recuperar senha', 'Fluxo de envio, validação e troca de senha; consulte os campos exigidos pela etapa enviada.')},
        '/listar_usuarios': {'get': operacao('Listar usuários', 'Exclusivo para ADM. Aceita o filtro opcional `tipo` (0, 1 ou 2).')},
        '/usuarios/{id_usuario}/status': {'put': operacao('Ativar/desativar usuário', 'Exclusivo para ADM. Ao desativar, `motivo` é obrigatório e é enviado por e-mail.', {
            'type': 'object', 'required': ['ativo'], 'properties': {'ativo': {'type': 'boolean'}, 'motivo': {'type': 'string'}}
        })},
        '/dados-perfil/{id_usuario}': {'get': operacao('Buscar perfil', 'Busca os dados de um perfil autorizado.')},
        '/editar-usuario/{id_usuario}': {'put': {
            **operacao('Editar perfil', 'Atualiza os campos do usuário autenticado ou administrado. Envie `multipart/form-data`; para cliente, `genero` é opcional e pode ser masculino, feminino ou outro.', None),
            'requestBody': {'content': {'multipart/form-data': {'schema': PERFIL}}},
        }},
        '/excluir-foto-perfil/{id_usuario}': {'delete': operacao('Excluir foto de perfil', 'Remove a foto de perfil do usuário.')},
        '/barbearias-disponiveis': {'get': operacao('Listar barbearias', 'Lista as barbearias cadastradas e a indicação de personalização.')},
        '/barbearia/servicos': {
            'get': operacao('Listar serviços', 'Lista os serviços da barbearia autenticada.'),
            'post': operacao('Criar serviço', 'Cria um serviço para posterior vínculo a funcionários. `duracao` é obrigatória, em minutos, e é usada para montar os horários disponíveis.', SERVICO),
        },
        '/barbearia/servicos/{id_servico}': {
            'put': operacao('Editar serviço', 'Atualiza nome, preço, duração em minutos e descrição de um serviço da barbearia autenticada.', SERVICO),
            'delete': operacao('Excluir serviço', 'Exclui um serviço pertencente à barbearia autenticada.'),
        },
        '/barbearia/personalizacao': {
            'get': operacao('Buscar personalização', 'Retorna cores, contatos, fotos, serviços, funcionários e dias. ADM pode informar `id_usuario` na query.'),
            'post': {
                **operacao('Criar personalização', 'Primeira personalização da barbearia. Envie `multipart/form-data`. É obrigatório cadastrar pelo menos um funcionário e informar `chave_pix`, `arkhe_client_id` e `arkhe_client_secret`.', None),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': PERSONALIZACAO}}},
            },
            'put': {
                **operacao('Editar personalização', 'Atualiza a personalização existente. Envie `multipart/form-data`. A barbearia deve manter pelo menos um funcionário e os dados de pagamento (chave Pix e credenciais Arkhé).', None),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': PERSONALIZACAO}}},
            },
        },
        '/fotos-perfil/{nome_arquivo}': {'get': operacao('Exibir foto de perfil', 'Entrega um arquivo de foto.', autenticada=False)},
        '/uploads/perfil/{nome_arquivo}': {'get': operacao('Exibir upload de perfil', 'Entrega um arquivo de perfil.', autenticada=False)},
        '/uploads/barbearia/{nome_arquivo}': {'get': operacao('Exibir imagem da barbearia', 'Entrega logo ou foto da barbearia.', autenticada=False)},
        '/visagismo/status': {'get': operacao(
            'Diagnóstico do visagismo',
            'Retorna se a OPENAI_API_KEY chega na rota (só prefixo), se a lib openai está instalada e quais modelos estão configurados. Sem autenticação.',
            autenticada=False)},
        '/visagismo/cortes': {
            'get': operacao(
                'Listar cortes do catálogo',
                'Público. Query opcional: id_barbearia + ids_servicos (ex: 1,2) filtram por categoria (cabelo/barba/barba_cabelo); ou passe categoria direto.',
                autenticada=False),
            'post': {
                **operacao('Criar corte', 'ADM ou barbearia. Envie multipart/form-data com nome, categoria e imagem (arquivo) ou imagem_url HTTPS.'),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': VISAGISMO_CORTE}}},
            },
        },
        '/visagismo/cortes/{id_corte}': {
            'put': {
                **operacao('Editar corte', 'ADM ou barbearia. Mesmos campos da criação; nova imagem substitui a anterior.'),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': VISAGISMO_CORTE}}},
            },
            'delete': operacao('Excluir corte', 'ADM ou barbearia. Exclusão lógica (ATIVO=0), preserva histórico e agendamentos.')},
        '/visagismo/analisar': {
            'post': {
                **operacao(
                    'Analisar foto (IA)',
                    'Logado. Multipart: imagem (JPG/PNG/WEBP até 10 MB), id_barbearia, ids_servicos. '
                    'A IA analisa a foto real (formato do rosto/cabelo existente) e devolve até 3 recomendações só com IDs do catálogo '
                    '(observacoes, cabelo_atual, categoria, recomendacoes, id_visagismo, foto_url). '
                    'Sem chave/lib no servidor cai em modo catálogo; com chave inválida retorna 502 com a causa (401/404/quota).'),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': {
                    'type': 'object',
                    'required': ['imagem', 'id_barbearia', 'ids_servicos'],
                    'properties': {
                        'imagem': {'type': 'string', 'format': 'binary'},
                        'id_barbearia': {'type': 'integer', 'example': 3},
                        'ids_servicos': {'type': 'string', 'example': '1,2'},
                    }}}}},
            },
        },
        '/visagismo/salvar-foto': {'post': {
            **operacao(
                'Salvar foto para simulação de cor',
                'Logado. Cria uma sessão de visagismo sem análise, destinada à simulação de pintura. Envie a imagem e os serviços selecionados em `multipart/form-data`.',
                None),
            'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': {
                'type': 'object',
                'required': ['imagem', 'id_barbearia', 'ids_servicos'],
                'properties': {
                    'imagem': {'type': 'string', 'format': 'binary'},
                    'id_barbearia': {'type': 'integer', 'example': 3},
                    'ids_servicos': {'type': 'string', 'example': '4'},
                },
            }}}},
        }},
        '/visagismo/{id_visagismo}/simular': {'post': operacao(
            'Gerar simulação do corte',
            'Logado. JSON {id_corte?, cor?, alvo?}; ao menos `id_corte` ou `cor` deve ser informado. `alvo` aceita cabelo, barba ou ambos. Edita a foto da sessão via OpenAI (images.edit, 1024x1024) com o prompt restrito do Teste-main: '
            'mantém a mesma pessoa/rosto/fundo e só altera o cabelo existente, sem criar cabelo, densidade, volume ou hairline. '
            'Retorna {imagem_url}. Sem chave/lib retorna 503; erro da OpenAI retorna 502.',
            {'type': 'object', 'properties': {
                'id_corte': {'type': 'integer', 'example': 1},
                'cor': {'type': 'string', 'example': '#5B3A29'},
                'alvo': {'type': 'string', 'enum': ['cabelo', 'barba', 'ambos'], 'default': 'ambos'},
            }})},
        '/uploads/visagismo/{tipo}/{nome}': {'get': operacao(
            'Exibir arquivo do visagismo',
            'tipo = cortes (público) | fotos | resultados (só dono ou ADM, via cookie).',
            autenticada=False)},
        '/agendamentos/horarios': {'get': operacao(
            'Listar horários disponíveis',
            'Público. Query obrigatória: id_barbearia, ids_servicos (ou servicos, ex: 1,2), data (AAAA-MM-DD). '
            'Query opcional id_funcionario: filtra a agenda do barbeiro (só dias dele, só ocupação dele; 404 se não for da barbearia, 400 se não atender os serviços). '
            'Retorna {data, duracao_minutos, funcionario, horarios: [{horario, fim, disponivel}]} com slots encadeados pela duração total dos serviços dentro do expediente.',
            autenticada=False)},
        '/agendamentos': {
            'get': operacao(
                'Listar agendamentos',
                'Logado. Cliente vê os próprios; barbearia vê os seus; ADM filtra por id_barbearia/id_usuario. '
                'Filtros opcionais status e data (AAAA-MM-DD). Retorna itens com cliente/barbearia/profissional/serviços, valor_total e `historico_atendimento`. '
                'Agendamentos não são concluídos automaticamente ao passar do horário e só são cancelados por ação do cliente ou da barbearia.'),
            'post': operacao(
                'Criar agendamento',
                'Logado. Cria o agendamento com status `agendado`, valida expediente, trava contra reserva dupla (409 se ocupado; por barbeiro quando id_funcionario informado) e vincula id_corte/id_visagismo quando vindos do visagismo. '
                'Retorna 201 com {id_agendamento, inicio_em, fim_em, id_funcionario}.',
                AGENDAMENTO)},
        '/agendamentos/{id_agendamento}/cancelar': {'put': operacao(
            'Cancelar agendamento',
            'Cliente dono, barbearia dona ou ADM. Marca como cancelado e envia e-mail à outra parte. Retorna {email_enviado}.')},
        '/agendamentos/{id_agendamento}/reagendar': {'put': operacao(
            'Reagendar',
            'Cliente dono, barbearia dona ou ADM. Body {data, horario, id_funcionario?}. Antes de enviar, consulte `/agendamentos/horarios` para mostrar somente as opções livres. Esta rota revalida expediente e ocupação (excluindo o próprio) e envia e-mail à outra parte.',
            {'type': 'object', 'required': ['data', 'horario'],
             'properties': {'data': {'type': 'string', 'format': 'date'}, 'horario': {'type': 'string', 'example': '14:30'},
                            'id_funcionario': {'type': 'integer'}}})},
        '/agendamentos/{id_agendamento}/avisar': {'post': operacao(
            'Avisar cliente',
            'Barbearia ou ADM. Body {texto até 500 caracteres}. Grava em AVISO e envia e-mail ao cliente. Retorna 201 com {email_enviado}.',
            {'type': 'object', 'required': ['texto'], 'properties': {'texto': {'type': 'string', 'example': 'Chegue com 10 minutos de antecedência.'}}})},
        '/agendamentos/{id_agendamento}/status-atendimento': {'put': operacao(
            'Registrar atendimento',
            "Barbearia dona ou ADM. Depois do fim do horário agendado, registra manualmente {status: 'concluido' ou 'faltou'} e adiciona o evento ao `historico_atendimento` devolvido pela listagem. Cliente não pode alterar este status.",
            {'type': 'object', 'required': ['status'], 'properties': {'status': {'type': 'string', 'enum': ['concluido', 'faltou']}}})},
        '/pagamentos/pix': {'post': operacao(
            'Gerar cobrança Pix (Arkhé)',
            'Logado (dono, barbearia ou ADM). Body {id_agendamento, valor?}. Calcula o valor pelos serviços quando omitido, cria a cobrança na Arkhé e registra em FINANCEIRO como pix_pendente. Retorna 201 com {id_cobranca, codigo_pagamento, valor, status}.',
            {'type': 'object', 'required': ['id_agendamento'], 'properties': {'id_agendamento': {'type': 'integer'}, 'valor': {'type': 'number'}}})},
        '/pagamentos/pix/{id_cobranca}': {'get': operacao(
            'Consultar cobrança Pix',
            'Logado. Consulta o status na Arkhé; se pago, marca pix_pago no FINANCEIRO. Retorna {pago, status}.')},
        '/pagamentos/boleto': {'post': operacao(
            'Gerar boleto do agendamento',
            'Logado. Body {id_agendamento}. Calcula o valor pelos serviços, cria a cobrança (ou simulado) e registra em FINANCEIRO como boleto_pendente. Retorna 201 com {url_boleto, codigo_pagamento, valor}.',
            {'type': 'object', 'required': ['id_agendamento'], 'properties': {'id_agendamento': {'type': 'integer'}}})},
        '/pagamentos/cartao': {'post': operacao(
            'Gerar checkout de cartão do agendamento',
            'Logado. Body {id_agendamento}. Calcula o valor pelos serviços e registra em FINANCEIRO como cartao_pendente. Retorna 201 com {url_checkout, valor}.',
            {'type': 'object', 'required': ['id_agendamento'], 'properties': {'id_agendamento': {'type': 'integer'}}})},
        '/pagamentos/na-hora': {'post': operacao(
            'Confirmar pagamento na barbearia',
            'Logado. Body {id_agendamento}. Registra em FINANCEIRO como `na_hora`. O agendamento continua com status `agendado` até ser concluído, marcado como falta ou cancelado manualmente.',
            {'type': 'object', 'required': ['id_agendamento'], 'properties': {'id_agendamento': {'type': 'integer'}}})},
        '/financeiro/grafico': {'get': operacao(
            'Gráfico financeiro (pygal)',
            'Barbearia ou ADM. Query data_inicio, data_fim (AAAA-MM-DD, máx. 92 dias) e tipo=todos|ganhos|custos. ADM pode filtrar id_barbearia. Retorna SVG de linha.')},
        '/financeiro/geral/resumo': {'get': operacao(
            'Resumo financeiro geral (ADM)',
            'ADM. Agregado do banco local (snapshot atualizado a cada visualização do dono da conta). Query data_inicio/data_fim. Retorna totais + por_barbearia.')},
        '/financeiro/geral/movimentacoes': {'get': operacao(
            'Movimentações gerais (ADM)',
            'ADM. Itemizado do banco local com barbearia_nome. Query data_inicio/data_fim.')},
        '/financeiro/geral/grafico': {'get': operacao(
            'Gráfico geral (ADM)',
            'ADM. SVG de linha agregado de todas as barbearias. Query data_inicio, data_fim e tipo.')},
        '/pagamentos/agendamento/{id_agendamento}': {'get': operacao(
            'Cobranças do agendamento',
            'Logado. Lista os registros FINANCEIRO vinculados ao agendamento.')},
        '/financeiro/conta': {'get': operacao('Consultar conta Arkhé', 'Barbearia ou ADM. Retorna os dados da conta financeira vinculada, quando configurada.')},
        '/financeiro/saldo': {'get': operacao('Consultar saldo', 'Barbearia ou ADM. Retorna {saldo, origem_dados}; usa dados Arkhé quando disponíveis e cálculo local como alternativa.')},
        '/financeiro/resumo': {'get': operacao('Resumo financeiro da barbearia', 'Barbearia ou ADM. Query opcional `data_inicio` e `data_fim` (AAAA-MM-DD, intervalo máximo de 92 dias). Retorna receitas, despesas e saldo do período.')},
        '/financeiro/movimentacoes': {'get': operacao('Movimentações financeiras da barbearia', 'Barbearia ou ADM. Query opcional `data_inicio` e `data_fim`. Retorna {movimentacoes, total, origem_dados}.')},
        '/financeiro/cobrancas/pix': {'post': operacao('Criar cobrança Pix avulsa', 'Barbearia ou ADM. Cria cobrança na conta financeira; não vincula um agendamento.', {
            'type': 'object', 'required': ['valor'], 'properties': {'valor': {'type': 'number', 'minimum': 0.01, 'example': 45.0}}
        })},
        '/financeiro/cobrancas/pix/{id_cobranca}': {'get': operacao('Consultar cobrança Pix avulsa', 'Barbearia ou ADM. Consulta uma cobrança Pix diretamente na Arkhé.')},
        '/financeiro/cobrancas/boleto': {'post': operacao('Criar boleto avulso', 'Barbearia ou ADM. Body {valor}. Quando Arkhé não suporta boleto, pode retornar um boleto simulado.', {
            'type': 'object', 'required': ['valor'], 'properties': {'valor': {'type': 'number', 'minimum': 0.01, 'example': 45.0}}
        })},
        '/financeiro/cobrancas/cartao': {'post': operacao('Criar checkout de cartão avulso', 'Barbearia ou ADM. Body {valor}. Quando Arkhé não suporta cartão, pode retornar checkout simulado.', {
            'type': 'object', 'required': ['valor'], 'properties': {'valor': {'type': 'number', 'minimum': 0.01, 'example': 45.0}}
        })},
        '/financeiro/cobrancas/na-hora': {'post': operacao('Registrar recebimento avulso na hora', 'Barbearia ou ADM. Body {valor}; confirma um recebimento sem criar cobrança externa.', {
            'type': 'object', 'required': ['valor'], 'properties': {'valor': {'type': 'number', 'minimum': 0.01, 'example': 45.0}}
        })},
        '/financeiro/cobrancas/boleto/{id_cobranca}': {'get': operacao('Consultar boleto avulso', 'Barbearia ou ADM. Consulta o boleto na Arkhé.')},
        '/financeiro/cobrancas/cartao/{id_cobranca}': {'get': operacao('Consultar checkout de cartão avulso', 'Barbearia ou ADM. Consulta o checkout na Arkhé.')},
        '/financeiro/webhook/arkhe': {'post': operacao('Receber webhook Arkhé', 'Endpoint de integração chamado pela Arkhé para notificações de pagamento. Não usa autenticação por cookie.', autenticada=False)},
        '/barbearias/{id_barbearia}/funcionarios': {'get': operacao(
            'Listar profissionais da barbearia',
            'Público. Retorna [{id_funcionario, nome, descricao, servicos, dias}] para o cliente escolher o barbeiro. '
            'Query opcional servicos=1,2 filtra só quem atende TODOS os serviços.',
            autenticada=False)},
    },
    'components': {'securitySchemes': {'cookieAuth': {'type': 'apiKey', 'in': 'cookie', 'name': 'access_token'}}},
}


@app.route('/openapi.json', methods=['GET'])
def openapi_json():
    """Contrato consumível por Swagger, Postman e outras ferramentas."""
    return jsonify(OPENAPI)


@app.route('/docs', methods=['GET'])
def documentacao_api():
    """Interface interativa equivalente ao `/docs` oferecido pelo FastAPI."""
    return render_template_string('''
<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cortaê API Docs</title><link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="swagger-ui"></div><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script><script>SwaggerUIBundle({url:'/openapi.json',dom_id:'#swagger-ui',persistAuthorization:true})</script></body></html>
''')
