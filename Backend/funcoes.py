import os
import re
import random
import datetime
import jwt
import smtplib

from flask import (
    request,
    render_template,
    current_app
)

from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from email.mime.text import MIMEText

from main import app


# ==========================================================
# BCRYPT
# ==========================================================

bcrypt = Bcrypt(app)


# ==========================================================
# SENHA FORTE
# ==========================================================

def verificar_senha_forte(senha):

    if not senha:
        return False, "Senha é obrigatória."

    if len(senha) < 8:
        return False, "A senha deve ter no mínimo 8 caracteres."

    if not re.search(r"[A-Z]", senha):
        return False, "A senha deve possuir uma letra maiúscula."

    if not re.search(r"[a-z]", senha):
        return False, "A senha deve possuir uma letra minúscula."

    if not re.search(r"[0-9]", senha):
        return False, "A senha deve possuir um número."

    if not re.search(r"[^A-Za-z0-9]", senha):
        return False, "A senha deve possuir um caractere especial."

    return True, "Senha válida."


# ==========================================================
# CRIPTOGRAFAR SENHA
# ==========================================================

def criptografar_senha(senha):

    return bcrypt.generate_password_hash(
        senha
    ).decode("utf-8")


# ==========================================================
# VERIFICAR SENHA
# ==========================================================

def verificar_senha(senha, senha_hash):

    return bcrypt.check_password_hash(
        senha_hash,
        senha
    )


# ==========================================================
# GERAR CÓDIGO
# ==========================================================

def gerar_codigo_verificacao():

    return str(
        random.randint(
            100000,
            999999
        )
    )


# ==========================================================
# ENVIAR EMAIL
# ==========================================================

def enviando_email(
        destinatario,
        assunto,
        mensagem,
        nome,
        codigo=None,
        mensagem_secundaria=None
):

    # Um aviso administrativo não possui código. Mantemos a mesma função para
    # todos os e-mails, mas enviamos ao template uma flag explícita para ele
    # não reservar a caixa laranja para textos como "—".
    codigo_texto = str(codigo or '').strip()
    exibir_codigo = bool(re.fullmatch(r'\d{6}', codigo_texto))

    user = current_app.config['MAIL_USER']
    senha = current_app.config['MAIL_PASSWORD']

    try:

        html = render_template(
            "ativacao.html",
            nome=nome,
            mensagem=mensagem,
            codigo=codigo_texto,
            mensagem_secundaria=mensagem_secundaria or '',
            exibir_codigo=exibir_codigo
        )

        msg = MIMEText(
            html,
            "html",
            "utf-8"
        )

        msg["Subject"] = assunto
        msg["From"] = user
        msg["To"] = destinatario

        server = smtplib.SMTP_SSL(
            current_app.config.get(
                'MAIL_SERVER',
                'smtp.gmail.com'
            ),
            current_app.config.get(
                'MAIL_PORT',
                465
            ),
            timeout=60
        )

        server.login(
            user,
            senha
        )

        server.send_message(
            msg
        )

        server.quit()

        return True

    except Exception as erro:

        print(
            "ERRO AO ENVIAR EMAIL:",
            erro
        )

        return False


# ==========================================================
# E-MAIL DE AVISO
# ==========================================================

def enviar_aviso_email(destinatario, nome, assunto, mensagem, remetente='Cortaê'):
    """Envia um comunicado textual sem reaproveitar o layout de código.

    Esta função é a base para futuros avisos enviados por uma barbearia. Ela
    centraliza a apresentação, evita HTML montado a partir de texto do usuário
    e preserva a função principal de envio em um único lugar.
    """
    return enviando_email(
        destinatario=destinatario,
        assunto=assunto,
        mensagem=mensagem,
        nome=nome,
        codigo=None,
        mensagem_secundaria=f'Enviado por: {remetente}'
    )


# ==========================================================
# GERAR TOKEN
# ==========================================================

def gerar_token(
        tipo,
        id_usuario,
        email=None,
        minutos=120
):

    payload = {

        'id_usuario':
            id_usuario,

        'tipo':
            tipo,

        'email':
            email,

        'exp':
            datetime.datetime.utcnow()
            + datetime.timedelta(
                minutes=minutos
            )
    }

    return jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )


# ==========================================================
# DECODIFICAR TOKEN
# ==========================================================

def decodificar_token():

    try:

        token = request.cookies.get(
            'access_token'
        )

        if not token:

            token = request.cookies.get(
                'acess_token'
            )

        if not token:

            authorization = request.headers.get(
                'Authorization'
            )

            if (
                    authorization
                    and authorization.startswith(
                'Bearer '
            )
            ):

                token = authorization[7:]

        if not token:

            return None

        payload = jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256']
        )

        return payload

    except jwt.ExpiredSignatureError:

        print(
            "TOKEN EXPIRADO."
        )

        return None

    except jwt.InvalidTokenError:

        print(
            "TOKEN INVÁLIDO."
        )

        return None

    except Exception as erro:

        print(
            "ERRO AO DECODIFICAR TOKEN:",
            erro
        )

        return None


# ==========================================================
# PASTA DE FOTOS
# ==========================================================

PASTA_FOTOS_PERFIL = app.config[
    'PERFIL_FOLDER'
]


# ==========================================================
# EXTENSÕES PERMITIDAS
# ==========================================================

EXTENSOES_IMAGEM = {

    '.jpg',
    '.jpeg',
    '.png',
    '.webp'

}


# ==========================================================
# BUSCAR FOTO DE PERFIL
# ==========================================================

def buscar_foto_perfil(id_usuario):

    print()
    print("==========================================")
    print("       BUSCANDO FOTO DE PERFIL")
    print("==========================================")

    print(
        "ID:",
        id_usuario
    )

    print(
        "Pasta:",
        PASTA_FOTOS_PERFIL
    )

    if not os.path.isdir(
            PASTA_FOTOS_PERFIL
    ):

        print(
            "Pasta não existe."
        )

        return None

    # ======================================================
    # PROCURAR FOTO
    # ======================================================

    for extensao in EXTENSOES_IMAGEM:

        caminho = os.path.join(

            PASTA_FOTOS_PERFIL,

            f'{id_usuario}{extensao}'

        )

        print(
            "Procurando:",
            caminho
        )

        if os.path.isfile(
                caminho
        ):

            print(
                "FOTO ENCONTRADA:",
                caminho
            )

            # IMPORTANTE:
            # URL usada pelo frontend

            return (
                f'/fotos-perfil/'
                f'{id_usuario}{extensao}'
            )

    print(
        "Nenhuma foto encontrada."
    )

    return None


# ==========================================================
# SALVAR FOTO DE PERFIL
# ==========================================================

def salvar_foto_perfil(
        arquivo,
        id_usuario
):

    print()
    print("==========================================")
    print("       SALVANDO FOTO DE PERFIL")
    print("==========================================")

    # ======================================================
    # VERIFICAR ARQUIVO
    # ======================================================

    if arquivo is None:

        raise ValueError(
            "Nenhuma foto foi enviada."
        )

    if not arquivo.filename:

        raise ValueError(
            "O arquivo enviado não possui nome."
        )

    print(
        "Arquivo recebido:",
        arquivo.filename
    )

    # ======================================================
    # NOME SEGURO
    # ======================================================

    nome_original = secure_filename(
        arquivo.filename
    )

    if not nome_original:

        raise ValueError(
            "Nome do arquivo inválido."
        )

    # ======================================================
    # EXTENSÃO
    # ======================================================

    extensao = os.path.splitext(
        nome_original
    )[1].lower()

    print(
        "Extensão:",
        extensao
    )

    # ======================================================
    # VALIDAR EXTENSÃO
    # ======================================================

    if extensao not in EXTENSOES_IMAGEM:

        raise ValueError(
            "Formato inválido. "
            "Use JPG, JPEG, PNG ou WEBP."
        )

    # ======================================================
    # CRIAR PASTA
    # ======================================================

    os.makedirs(
        PASTA_FOTOS_PERFIL,
        exist_ok=True
    )

    # ======================================================
    # APAGAR TODAS AS FOTOS ANTIGAS
    # ======================================================

    for extensao_antiga in EXTENSOES_IMAGEM:

        caminho_antigo = os.path.join(

            PASTA_FOTOS_PERFIL,

            f'{id_usuario}{extensao_antiga}'

        )

        if os.path.isfile(
                caminho_antigo
        ):

            try:

                os.remove(
                    caminho_antigo
                )

                print(
                    "Foto antiga removida:",
                    caminho_antigo
                )

            except Exception as erro:

                raise ValueError(
                    "Não foi possível remover "
                    f"a foto antiga: {erro}"
                )

    # ======================================================
    # CAMINHO NOVO
    # ======================================================

    caminho_final = os.path.join(

        PASTA_FOTOS_PERFIL,

        f'{id_usuario}{extensao}'

    )

    print(
        "Salvando em:",
        caminho_final
    )

    # ======================================================
    # GARANTIR INÍCIO DO ARQUIVO
    # ======================================================

    try:

        arquivo.stream.seek(0)

    except Exception:

        pass

    # ======================================================
    # SALVAR
    # ======================================================

    try:

        arquivo.save(
            caminho_final
        )

    except Exception as erro:

        print(
            "ERRO AO SALVAR:",
            erro
        )

        raise ValueError(
            f"Não foi possível salvar a foto: {erro}"
        )

    # ======================================================
    # VERIFICAR ARQUIVO
    # ======================================================

    if not os.path.isfile(
            caminho_final
    ):

        raise ValueError(
            "A foto não foi criada."
        )

    tamanho = os.path.getsize(
        caminho_final
    )

    if tamanho <= 0:

        try:

            os.remove(
                caminho_final
            )

        except Exception:

            pass

        raise ValueError(
            "A foto foi salva vazia."
        )

    print(
        "FOTO SALVA COM SUCESSO!"
    )

    print(
        "Arquivo:",
        caminho_final
    )

    print(
        "Tamanho:",
        tamanho,
        "bytes"
    )

    print(
        "=========================================="
    )

    # ======================================================
    # RETORNAR URL
    # ======================================================

    return (
        f'/fotos-perfil/'
        f'{id_usuario}{extensao}'
    )


# ==========================================================
# EXCLUIR FOTO DE PERFIL
# ==========================================================

def excluir_foto_perfil(id_usuario):

    print()
    print("==========================================")
    print("       EXCLUINDO FOTO DE PERFIL")
    print("==========================================")

    foto_excluida = False

    for extensao in EXTENSOES_IMAGEM:

        caminho = os.path.join(

            PASTA_FOTOS_PERFIL,

            f'{id_usuario}{extensao}'

        )

        if os.path.isfile(
                caminho
        ):

            try:

                os.remove(
                    caminho
                )

                print(
                    "Foto removida:",
                    caminho
                )

                foto_excluida = True

            except Exception as erro:

                print(
                    "Erro ao excluir foto:",
                    erro
                )

                raise ValueError(
                    f"Não foi possível excluir a foto: {erro}"
                )

    return foto_excluida
