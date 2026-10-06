import os
from flask import Flask
import firebirdsql as fdb
from flask_cors import CORS


# ==========================================================
# APLICAÇÃO
# ==========================================================

app = Flask(__name__)

app.config.from_pyfile('config.py')

_chave_openai = (app.config.get('OPENAI_API_KEY') or '').strip()
print(
    'OPENAI_API_KEY:',
    f"CONFIGURADA (prefixo {(_chave_openai[:7] + '...') if len(_chave_openai) >= 7 else 'curta demais'} len={len(_chave_openai)})"
    if _chave_openai else 'AUSENTE (verifique Backend/.env -> OPENAI_API_KEY)'
)
print('VISAGISMO_ANALYSIS_MODEL:', app.config.get('VISAGISMO_ANALYSIS_MODEL'))
print('VISAGISMO_IMAGE_MODEL:', app.config.get('VISAGISMO_IMAGE_MODEL'))
try:
    import openai  # noqa: F401
    print('openai lib: OK')
except ImportError:
    print('openai lib: AUSENTE (pip install -r requirements.txt)')



# ==========================================================
# CORS
# ==========================================================

CORS(
    app,

    supports_credentials=True,

    resources={
        r"/*": {
            # Libera o uso por qualquer IP/domínio sem cadastro prévio.
            # Com credentials, o Flask-CORS reflete a origem da requisição.
            "origins": "*",

            "methods": [
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "OPTIONS"
            ],

            "allow_headers": [
                "Content-Type",
                "Authorization"
            ],

            "supports_credentials": True
        }
    }
)


# ==========================================================
# FIREBIRD
# ==========================================================

FBCLIENT = (
    r"C:\Program Files (x86)\Firebird\Firebird_5_0\fbclient.dll"
)


# ==========================================================
# CONEXÃO COM FIREBIRD
# ==========================================================

def conectar_banco():

    return fdb.connect(
        host=app.config['DB_HOST'],
        database=app.config['DB_NAME'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASSWORD'],
        charset='UTF8'
    )


# ==========================================================
# TESTAR BANCO
# ==========================================================

try:

    con = conectar_banco()

    print("==========================================")
    print(" FIREBIRD CONECTADO COM SUCESSO!")
    print("==========================================")

    # Criar sequences necessárias para auto increment
    cursor = con.cursor()

    # (sequence, tabela, coluna da chave primária)
    sequences_necessarias = [
        ('SEQ_FINANCEIRO', 'FINANCEIRO', 'ID_FINANCEIRO'),
        ('SEQ_USUARIO', 'USUARIO', 'ID_USUARIO'),
        ('SEQ_AGENDAMENTO', 'AGENDAMENTO', 'ID_AGENDAMENTO'),
        ('SEQ_CORTE_VISAGISMO', 'CORTE_VISAGISMO', 'ID_CORTE'),
        ('SEQ_VISAGISMO_SESSAO', 'VISAGISMO_SESSAO', 'ID_VISAGISMO'),
        ('SEQ_PERSONALIZACAO', 'PERSONALIZACAO', 'ID_PERSONALIZACAO'),
        ('SEQ_DIA', 'DIAS_DE_SERVICO', 'ID_DIA'),
        ('SEQ_FUNCIONARIO', 'FUNCIONARIO', 'ID_FUNCIONARIO'),
        ('SEQ_FUNCIONARIO_DIA', 'FUNCIONARIO_DIA', 'ID_FUNCIONARIO_DIA'),
        ('SEQ_SERVICO', 'SERVICO', 'ID_SERVICO'),
        ('SEQ_SERVICO_POR_FUNCIONARIO', 'SERVICO_POR_FUNCIONARIO', 'ID_SERVI_FUNCI'),
        ('SEQ_FINANCEIRO_SNAPSHOT', 'FINANCEIRO_SNAPSHOT', 'ID_SNAPSHOT'),
        ('SEQ_AVISO', 'AVISO', 'ID_AVISO'),
    ]
    for seq, tabela, coluna in sequences_necessarias:
        cursor.execute(f"SELECT 1 FROM RDB$GENERATORS WHERE TRIM(RDB$GENERATOR_NAME) = '{seq}'")
        if not cursor.fetchone():
            try:
                cursor.execute(f'CREATE SEQUENCE {seq}')
            except Exception:
                pass

        cursor.execute(f'SELECT COALESCE(MAX({coluna}), 0) FROM {tabela}')
        maior_id = int(cursor.fetchone()[0] or 0)
        cursor.execute(f'SET GENERATOR {seq} TO {maior_id}')

    cursor.execute("""
        SELECT 1 FROM RDB$RELATION_FIELDS
        WHERE RDB$RELATION_NAME = 'USUARIO'
          AND TRIM(RDB$FIELD_NAME) = 'JA_BLOQUEADO'
    """)
    if not cursor.fetchone():
        cursor.execute('ALTER TABLE USUARIO ADD JA_BLOQUEADO SMALLINT DEFAULT 0')

    # Público-alvo de cada serviço. A seleção não depende mais do texto do
    # nome ("Corte Feminino", por exemplo); ela é um dado explícito.
    cursor.execute("""
        SELECT 1 FROM RDB$RELATION_FIELDS
        WHERE RDB$RELATION_NAME = 'SERVICO'
          AND TRIM(RDB$FIELD_NAME) = 'GENERO'
    """)
    if not cursor.fetchone():
        cursor.execute('ALTER TABLE SERVICO ADD GENERO VARCHAR(10)')
        # No Firebird uma coluna criada por DDL só pode ser usada após commit.
        con.commit()

    # Migra serviços antigos uma única vez. Os que não possuíam indicação
    # confiável recebem "unissex", para não excluir clientes indevidamente.
    cursor.execute("""
        UPDATE SERVICO
        SET GENERO = CASE
            WHEN LOWER(NOME_SERVICO) CONTAINING 'feminino'
              OR LOWER(NOME_SERVICO) CONTAINING 'feminina'
              OR LOWER(NOME_SERVICO) CONTAINING 'femenino'
              OR LOWER(NOME_SERVICO) CONTAINING 'mulher'
              OR LOWER(NOME_SERVICO) CONTAINING 'noiva'
              OR LOWER(NOME_SERVICO) CONTAINING 'madrinha'
                THEN 'feminino'
            WHEN LOWER(NOME_SERVICO) CONTAINING 'masculino'
              OR LOWER(NOME_SERVICO) CONTAINING 'masculina'
              OR LOWER(NOME_SERVICO) CONTAINING 'homem'
              OR LOWER(NOME_SERVICO) CONTAINING 'noivo'
              OR LOWER(NOME_SERVICO) CONTAINING 'padrinho'
              OR LOWER(NOME_SERVICO) CONTAINING 'barba'
              OR LOWER(NOME_SERVICO) CONTAINING 'bigode'
                THEN 'masculino'
            ELSE 'unissex'
        END
        WHERE GENERO IS NULL OR TRIM(GENERO) = ''
    """)

    con.commit()
    cursor.close()

    con.close()

except Exception as erro:

    print("ERRO FIREBIRD:")
    print(erro)


# ==========================================================
# IMPORTAR ROTAS
# ==========================================================

from view import *
from Listar_usuario import *
import arkhe  # Importa rotas de financeiro/arkhé

if __name__ == '__main__':  
    # 3. Iniciar o servidor Flask normalmente (Link Local)
    print("Iniciando servidor local...")
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Evita que o ngrok tente abrir dois túneis ao mesmo tempo no modo debug
    )
