from flask import request, jsonify, render_template
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import smtplib

from main import app, conectar_banco

from funcoes import (
    verificar_senha_forte,
    criptografar_senha,
    gerar_codigo_verificacao,
    enviando_email,
    decodificar_token
)


# ==========================================
# ENVIAR E-MAIL
# ==========================================

def enviar_email_ativacao(email_destino, nome, codigo):

    html = render_template(
        'ativacao.html',
        nome=nome,
        codigo=codigo
    )

    mensagem = MIMEMultipart('alternative')

    mensagem['Subject'] = 'Ative sua conta - Cortaê'
    mensagem['From'] = app.config['EMAIL_FROM']
    mensagem['To'] = email_destino

    mensagem.attach(
        MIMEText(
            html,
            'html',
            'utf-8'
        )
    )

    servidor = smtplib.SMTP(
        app.config['EMAIL_HOST'],
        app.config['EMAIL_PORT']
    )

    servidor.starttls()

    servidor.login(
        app.config['EMAIL_USER'],
        app.config['EMAIL_PASSWORD']
    )

    servidor.sendmail(
        app.config['EMAIL_FROM'],
        email_destino,
        mensagem.as_string()
    )

    servidor.quit()


# ==========================================
# CADASTRO
# ==========================================

@app.route('/cadastro', methods=['POST'])
def cadastro():

    con = None

    try:

        dados = request.get_json(silent=True)

        if not dados:
            return jsonify({
                'mensagem': {"informacao":'Envie os dados em formato JSON.',
                             "tipo":"erro"}
            }), 400

        nome = str(dados.get('nome') or '').strip()
        email = str(dados.get('email') or '').strip().replace(' ', '')
        telefone = str(dados.get('telefone') or '').strip()
        senha = dados.get('senha')
        confirmar_senha = dados.get('confirmarSenha')
        tipo = dados.get('tipo')
        genero = str(dados.get('genero') or '').strip().lower()

        # ==========================================
        # CAMPOS OBRIGATÓRIOS
        # ==========================================

        if not nome:
            return jsonify({
                'mensagem': {"informacao":'Nome é obrigatório.',
                             "tipo":"erro"}
            }), 400

        if not email:
            return jsonify({
                'mensagem': {"informacao":'E-mail é obrigatório.',
                         "tipo":"erro"}
            }), 400

        if not telefone:
            return jsonify({
                'mensagem': {"informacao":'Telefone é obrigatório.',
                         "tipo":"erro"}
            }), 400

        if not re.match(r'^[A-Za-zÀ-ÿ ]+$', nome):
            return jsonify({
                'mensagem': {"informacao":'O nome deve conter apenas letras e espaços.',
                             "tipo":"erro"}
            }), 400

        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({
                'mensagem': {"informacao":'E-mail inválido.', "tipo":"erro"}
            }), 400

        if len(''.join(filter(str.isdigit, telefone))) not in (10, 11):
            return jsonify({
                'mensagem': {"informacao":'Telefone inválido.', "tipo":"erro"}
            }), 400

        telefone_numeros = ''.join(filter(str.isdigit, telefone))
        if len(telefone_numeros) not in (10, 11):
            return jsonify({
                'mensagem': {'informacao': 'Telefone inválido.', 'tipo': 'erro'}
            }), 400


        if not senha:
            return jsonify({
                'mensagem': {"informacao":'Senha é obrigatória.',
                             "tipo":"erro"}
            }), 400

        if not confirmar_senha:
            return jsonify({
                'mensagem': {"informacao":'Confirmação de senha é obrigatória.',
                             "tipo":"erro"}
            }), 400

        if tipo is None:
            return jsonify({
                'mensagem': {"informacao":'Tipo de usuário é obrigatório.',
                             "tipo":"erro"}
            }), 400

        # ==========================================
        # CONFIRMAR SENHA
        # ==========================================

        if senha != confirmar_senha:

            return jsonify({
                'mensagem': {"informacao":'As senhas não coincidem.',
                             "tipo":"erro"}
            }), 400

        # ==========================================
        # VERIFICAR SENHA FORTE
        # ==========================================

        senha_valida, mensagem_senha = verificar_senha_forte(
            senha
        )

        if not senha_valida:

            return jsonify({
                'mensagem': {"informacao":mensagem_senha,
                             "tipo":"erro"}
            }), 400

        # ==========================================
        # VALIDAR TIPO
        # ==========================================

        try:

            tipo = int(tipo)

        except (ValueError, TypeError):

            return jsonify({
                'mensagem': {"informacao":'Tipo de usuário inválido.',
                             "tipo":"erro"}
            }), 400

        if tipo not in [0, 1, 2]:

            return jsonify({
                'mensagem': {'informacao': 'Tipo de usuário inválido.', 'tipo': 'erro'}
            }), 400

        if genero and genero not in ['masculino', 'feminino', 'outro']:
            return jsonify({
                'mensagem': {'informacao': 'Gênero inválido. Use: masculino, feminino ou outro.', 'tipo': 'erro'}
            }), 400

        # ==========================================
        # CONECTAR BANCO
        # ==========================================

        con = conectar_banco()

        cursor = con.cursor()

        # ==========================================
        # VERIFICAR SE EMAIL JÁ EXISTE
        # ==========================================

        cursor.execute(
            '''
            SELECT ID_USUARIO
            FROM USUARIO
            WHERE EMAIL = ?
            ''',
            (email,)
        )

        usuario_existente = cursor.fetchone()

        if usuario_existente:

            return jsonify({
                'mensagem': {"informacao":'Este e-mail já está cadastrado.',
                             "tipo":"erro"}
            }), 409

        # ==========================================
        # GERAR ID (usando sequence do Firebird)
        # ==========================================

        cursor.execute('SELECT NEXT VALUE FOR SEQ_USUARIO FROM RDB$DATABASE')
        id_usuario = cursor.fetchone()[0]

        # ==========================================
        # CRIPTOGRAFAR SENHA
        # ==========================================

        senha_hash = criptografar_senha(
            senha
        )

        # ==========================================
        # GERAR CÓDIGO
        # ==========================================

        codigo = gerar_codigo_verificacao()

        # ==========================================
        # CADASTRAR USUÁRIO
        # ==========================================

        cursor.execute(
            '''
            INSERT INTO USUARIO
            (
                ID_USUARIO,
                NOME,
                EMAIL,
                TELEFONE,
                SENHA_HASH,
                TIPO,
                TENTATIVA,
                ATIVO,
                CODIGO_VERIFICACAO,
                GENERO
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?,
                0,
                0,
                ?,
                ?
            )
            ''',
            (
                id_usuario,
                nome,
                email,
                telefone_numeros,
                senha_hash,
                tipo,
                codigo,
                genero if genero else None
            )
        )

        # ==========================================
        # SALVAR NO BANCO
        # ==========================================

        con.commit()

        cursor.close()
        con.close()

        con = None

        # ==========================================
        # ENVIAR EMAIL
        # ==========================================

        email_enviado = enviando_email(
            destinatario=email,
            assunto='Confirmação de cadastro - Cortaê',
            mensagem='Seu cadastro foi realizado com sucesso!',
            codigo=codigo,
            nome=nome,
            mensagem_secundaria=(
                'Utilize o código abaixo para confirmar '
                'seu endereço de e-mail.'
            )
        )

        # ==========================================
        # VERIFICAR ENVIO
        # ==========================================

        if not email_enviado:
            return jsonify({
                'mensagem':{"informacao":'Cadastro realizado, mas não foi possível '
                    'enviar o e-mail de confirmação.',"tipo":"erro"}

            }), 500

        # ==========================================
        # SUCESSO
        # ==========================================

        return jsonify({
            'mensagem':{"informacao":'Cadastro realizado com sucesso! '
                                    'Um código de confirmação foi enviado '
                                    'para seu e-mail.',
                        "tipo":"sucesso"}

        }), 201

    except Exception as erro:

        if con:

            con.rollback()

        return jsonify({
            'mensagem': {"informacao":'Erro ao realizar cadastro.',"tipo":"erro"},
            'detalhes': str(erro)
        }), 500

    finally:

        if con:

            con.close()


# ==========================================
# VERIFICAR CÓDIGO
# ==========================================

@app.route('/verificar-codigo', methods=['POST'])
def verificar_codigo():

    con = None

    try:

        dados = request.get_json(silent=True)

        if not dados:
            return jsonify({
                'mensagem': {
                    'informacao': 'Envie os dados em formato JSON.',
                    'tipo': 'erro'
                }
            }), 400

        email = dados.get('email')
        codigo = dados.get('codigo')

        if not email:
            return jsonify({
                'mensagem': {
                    'informacao': 'E-mail é obrigatório.',
                    'tipo': 'erro'
                }
            }), 400

        if not codigo:
            return jsonify({
                'mensagem': {
                    'informacao': 'Código de ativação é obrigatório.',
                    'tipo': 'erro'
                }
            }), 400

        email = str(email).strip()
        codigo = str(codigo).strip()

        con = conectar_banco()
        cursor = con.cursor()

        cursor.execute(
            '''
            SELECT
                ID_USUARIO,
                CODIGO_VERIFICACAO,
                ATIVO
            FROM USUARIO
            WHERE EMAIL = ?
            ''',
            (email,)
        )

        usuario = cursor.fetchone()

        if not usuario:

            return jsonify({
                'mensagem': {
                    'informacao': 'Usuário não encontrado.',
                    'tipo': 'erro'
                }
            }), 404

        id_usuario = usuario[0]
        codigo_banco = usuario[1]
        ativo = usuario[2]

        if int(ativo or 0) == 1:

            return jsonify({
                'mensagem': {
                    'informacao': 'Esta conta já está ativada.',
                    'tipo': 'sucesso'
                }
            }), 200

        # ==========================================
        # CÓDIGO NÃO EXISTE
        # ==========================================

        if codigo_banco is None:

            return jsonify({
                'mensagem': {
                    'informacao': 'Código de ativação não encontrado.',
                    'tipo': 'erro'
                }
            }), 400

        # ==========================================
        # COMPARAR CÓDIGO
        # ==========================================

        if codigo != str(codigo_banco).strip():

            return jsonify({
                'mensagem': {
                    'informacao': 'Código de verificação inválido.',
                    'tipo': 'erro'
                }
            }), 400

        # ==========================================
        # ATIVAR USUÁRIO
        # ==========================================

        cursor.execute(
            '''
            UPDATE USUARIO
            SET
                ATIVO = 1,
                EMAIL_CONFIRMADO = 1,
                CODIGO_VERIFICACAO = NULL
            WHERE ID_USUARIO = ?
            ''',
            (id_usuario,)
        )

        con.commit()

        return jsonify({
            'mensagem': {
                'informacao': 'E-mail confirmado com sucesso! Sua conta foi ativada.',
                'tipo': 'sucesso'
            }
        }), 200

    except Exception as erro:

        if con:
            con.rollback()

        return jsonify({
            'mensagem': {
                'informacao': 'Erro ao verificar código.',
                'tipo': 'erro'
            },
            'detalhes': str(erro)
        }), 500

    finally:

        if con:
            con.close()

