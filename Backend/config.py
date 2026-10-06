import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

load_dotenv(
    os.path.join(BASE_DIR, '.env'),
    override=True
)


# ==========================================================
# SEGURANÇA
# ==========================================================

SECRET_KEY = 'minhasenhasupersecretacomçe~´`^antihackeramericanoerusso'

DEBUG = True


# ==========================================================
# DIRETÓRIO PRINCIPAL DO BACKEND
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# ==========================================================
# FIREBIRD
# ==========================================================

DB_HOST = 'localhost'

DB_NAME = os.path.join(
    BASE_DIR,
    'CORTAE.FDB'
)

DB_USER = 'SYSDBA'

DB_PASSWORD = 'sysdba'


# ==========================================================
# EMAIL - GMAIL
# ==========================================================

MAIL_USER = 'mauroauroadm@gmail.com'

MAIL_PASSWORD = 'dyql srcx kqss zqpz'


# ==========================================================
# SMTP
# ==========================================================

MAIL_SERVER = 'smtp.gmail.com'

MAIL_PORT = 465


# ==========================================================
# UPLOADS
# ==========================================================

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    'uploads'
)


# ==========================================================
# FOTOS DE PERFIL
# ==========================================================

PERFIL_FOLDER = os.path.join(
    UPLOAD_FOLDER,
    'perfil'
)


# ==========================================================
# VISAGISMO
# ==========================================================
# Configure a chave apenas pelo ambiente do servidor, nunca no repositório.
def _limpar_env(nome, padrao=None):
    valor = os.getenv(nome, padrao)
    if valor is None:
        return None
    valor = valor.strip().strip('"').strip("'").strip()
    return valor or None


OPENAI_API_KEY = _limpar_env('OPENAI_API_KEY')
VISAGISMO_ANALYSIS_MODEL = os.getenv('VISAGISMO_ANALYSIS_MODEL', 'gpt-5.6-terra')
VISAGISMO_IMAGE_MODEL = os.getenv('VISAGISMO_IMAGE_MODEL', 'gpt-image-2')
VISAGISMO_FOLDER = os.path.join(UPLOAD_FOLDER, 'visagismo')
VISAGISMO_CORTES_FOLDER = os.path.join(VISAGISMO_FOLDER, 'cortes')
VISAGISMO_FOTOS_FOLDER = os.path.join(VISAGISMO_FOLDER, 'fotos')
VISAGISMO_RESULTADOS_FOLDER = os.path.join(VISAGISMO_FOLDER, 'resultados')
MAX_VISAGISMO_IMAGE_BYTES = 10 * 1024 * 1024


# ==========================================================
# PAGAMENTO ARKHÉ (PIX)
# ==========================================================
# Credenciais da integração PJ ficam só no servidor (.env).

ARKHE_CLIENT_ID = _limpar_env('ARKHE_CLIENT_ID')

ARKHE_CLIENT_SECRET = _limpar_env('ARKHE_CLIENT_SECRET')

ARKHE_BASE_URL = (_limpar_env('ARKHE_BASE_URL') or 'https://arkhe-backend.zbbquj.easypanel.host').rstrip('/')


# ==========================================================
# PASTAS FINANCEIRO / ARKHÉ
# ==========================================================

FINANCEIRO_FOLDER = os.path.join(UPLOAD_FOLDER, 'financeiro')
COMPROVANTES_FOLDER = os.path.join(FINANCEIRO_FOLDER, 'comprovantes')
