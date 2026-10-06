from flask import jsonify, request, make_response
import jwt
from datetime import datetime, timedelta

from main import app, conectar_banco

from funcoes import (
    verificar_senha,
    gerar_codigo_verificacao,
    enviando_email
)


# ==========================================================
# LOGIN
# ==========================================================

@app.route('/login', methods=['POST'])
def login():

    con = None
    cursor = None

    try:

        # ==================================================
        # RECEBER JSON
        # ==================================================

        dados = request.get_json(silent=True)

        if not dados:

            return jsonify({
                'mensagem': {
                    'informacao': 'Dados não enviados.',
                    'tipo': 'erro'
                }
            }), 400


        # ==================================================
        # PEGAR DADOS
        # ==================================================

        email = dados.get('email')
        senha = dados.get('senha')


        if isinstance(email, str):

            email = (
                email
                .strip()
                .replace(' ', '')
            )


        # ==================================================
        # VALIDAR EMAIL
        # ==================================================

        if not email:

            return jsonify({
                'mensagem': {
                    'informacao': 'O email é obrigatório.',
                    'tipo': 'erro'
                }
            }), 400


        # ==================================================
        # VALIDAR SENHA
        # ==================================================

        if not senha:

            return jsonify({
                'mensagem': {
                    'informacao': 'A senha é obrigatória.',
                    'tipo': 'erro'
                }
            }), 400


        # ==================================================
        # CONECTAR AO BANCO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()


        # ==================================================
        # BUSCAR USUÁRIO
        # ==================================================

        cursor.execute("""
            SELECT
                ID_USUARIO,
                NOME,
                EMAIL,
                TELEFONE,
                SENHA_HASH,
                TIPO,
                ATIVO,
                EMAIL_CONFIRMADO,
                TENTATIVA,
                GENERO
            FROM USUARIO
            WHERE EMAIL = ?
        """, (
            email,
        ))


        usuario = cursor.fetchone()


        # ==================================================
        # USUÁRIO NÃO ENCONTRADO
        # ==================================================

        if not usuario:

            return jsonify({
                'mensagem': {
                    'informacao': 'Email ou senha incorretos.',
                    'tipo': 'erro'
                }
            }), 401


        # ==================================================
        # DADOS DO USUÁRIO
        # ==================================================

        id_usuario = usuario[0]
        nome = usuario[1]
        email_banco = usuario[2]
        telefone = usuario[3]
        senha_hash = usuario[4]
        tipo = usuario[5]
        ativo = usuario[6]
        email_confirmado = usuario[7]
        tentativas = usuario[8] or 0


        # ==================================================
        # VERIFICAR EMAIL
        # ==================================================

        if email_confirmado != 1:

            codigo = gerar_codigo_verificacao()


            # ==================================================
            # SALVAR CÓDIGO
            # ==================================================

            cursor.execute("""
                UPDATE USUARIO
                SET CODIGO_VERIFICACAO = ?
                WHERE ID_USUARIO = ?
            """, (
                codigo,
                id_usuario
            ))

            con.commit()


            # ==================================================
            # ENVIAR EMAIL
            # ==================================================

            email_enviado = enviando_email(
                destinatario=email_banco,
                assunto='Confirmação de cadastro - Cortaê',
                mensagem='Seu cadastro foi realizado com sucesso!',
                codigo=codigo,
                nome=nome,
                mensagem_secundaria=(
                    'Utilize o código abaixo para confirmar '
                    'seu endereço de e-mail.'
                )
            )


            if not email_enviado:

                return jsonify({
                    'mensagem': {
                        'informacao': (
                            'Seu e-mail ainda não foi confirmado, '
                            'mas não foi possível enviar o código '
                            'de verificação.'
                        ),
                        'tipo': 'erro'
                    }
                }), 500


            return jsonify({

                'mensagem': {
                    'informacao': (
                        'Seu e-mail ainda não foi confirmado. '
                        'Um novo código de verificação foi enviado '
                        'para seu e-mail.'
                    ),
                    'tipo': 'aviso'
                },

                'email_confirmacao': True

            }), 403


        # ==================================================
        # VERIFICAR USUÁRIO BLOQUEADO
        # ==================================================

        if ativo == 2:

            return jsonify({
                'mensagem': {
                    'informacao': (
                        'Usuário bloqueado após exceder '
                        'o limite de tentativas de login.'
                    ),
                    'tipo': 'erro'
                }
            }), 403


        # ==================================================
        # VERIFICAR USUÁRIO INATIVO
        # ==================================================

        if ativo != 1:

            return jsonify({
                'mensagem': {
                    'informacao': 'Usuário inativo.',
                    'tipo': 'erro'
                }
            }), 403


        # ==================================================
        # VERIFICAR SENHA
        # ==================================================

        senha_correta = verificar_senha(
            senha,
            senha_hash
        )


        # ==================================================
        # SENHA INCORRETA
        # ==================================================

        if not senha_correta:

            novas_tentativas = tentativas + 1


            # ==================================================
            # BLOQUEAR APÓS 3 TENTATIVAS
            # ==================================================

            if novas_tentativas >= 3:

                cursor.execute("""
                    UPDATE USUARIO
                    SET
                        TENTATIVA = ?,
                        ATIVO = 2
                    WHERE ID_USUARIO = ?
                """, (
                    novas_tentativas,
                    id_usuario
                ))

                con.commit()


                return jsonify({
                    'mensagem': {
                        'informacao': (
                            'Usuário bloqueado após 3 '
                            'tentativas de login incorretas.'
                        ),
                        'tipo': 'erro'
                    }
                }), 403


            # ==================================================
            # SALVAR TENTATIVA
            # ==================================================

            cursor.execute("""
                UPDATE USUARIO
                SET TENTATIVA = ?
                WHERE ID_USUARIO = ?
            """, (
                novas_tentativas,
                id_usuario
            ))

            con.commit()


            restantes = 3 - novas_tentativas


            return jsonify({
                'mensagem': {
                    'informacao': (
                        'Email ou senha incorretos. '
                        f'Você possui {restantes} '
                        'tentativa(s) restante(s).'
                    ),
                    'tipo': 'erro'
                }
            }), 401


        # ==================================================
        # SENHA CORRETA
        # ==================================================

        cursor.execute("""
            UPDATE USUARIO
            SET TENTATIVA = 0
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))

        con.commit()


        # ==================================================
        # GERAR JWT
        # ==================================================

        token = jwt.encode(

            {
                'id_usuario': id_usuario,
                'email': email_banco,
                'tipo': tipo,
                'exp': (
                    datetime.utcnow()
                    + timedelta(hours=2)
                )
            },

            app.config['SECRET_KEY'],

            algorithm='HS256'
        )


        # ==================================================
        # RESPOSTA
        # ==================================================

        resposta = jsonify({

            'mensagem': {
                'informacao': 'Login realizado com sucesso.',
                'tipo': 'sucesso'
            },

            'usuario': {

                'id_usuario': id_usuario,

                'id': id_usuario,

                'nome': nome,

                'email': email_banco,

                'telefone': telefone,

                'tipo': tipo,

                'genero': usuario[9] if len(usuario) > 9 else None
            }
        })

        # ==========================================================
        # SALVAR JWT NO COOKIE
        # ==========================================================

        resposta.set_cookie(
            key='access_token',
            value=token,
            max_age=7200,
            httponly=True,
            secure=False,
            samesite='Lax',
            path='/'
        )


        return resposta, 200


    # ======================================================
    # ERRO
    # ======================================================

    except Exception as erro:

        if con:

            try:
                con.rollback()
            except Exception:
                pass


        print(
            'ERRO NO LOGIN:',
            erro
        )


        return jsonify({

            'mensagem': {
                'informacao': 'Erro interno no servidor.',
                'tipo': 'erro'
            },

            'detalhes': str(erro)

        }), 500


    # ======================================================
    # FECHAR BANCO
    # ======================================================

    finally:

        if cursor:

            try:
                cursor.close()
            except Exception:
                pass


        if con:

            try:
                con.close()
            except Exception:
                pass


# ==========================================================
# LOGOUT
# ==========================================================

@app.route('/logout', methods=['POST'])
def logout():

    resposta = make_response(
        jsonify({
            'mensagem': {
                'informacao': 'Logout realizado com sucesso!',
                'tipo': 'sucesso'
            }
        }),
        200
    )

    resposta.delete_cookie(
        'access_token',
        path='/'
    )

    resposta.delete_cookie(
        'acess_token',
        path='/'
    )

    return resposta