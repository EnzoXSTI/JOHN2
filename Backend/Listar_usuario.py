from flask import request, jsonify
from main import app, conectar_banco
from funcoes import decodificar_token, buscar_foto_perfil, enviando_email


@app.route('/listar_usuarios', methods=['GET'])
def listar_usuarios():
    con = None
    cursor = None
    try:
        token = decodificar_token()
        if not token or int(token.get('tipo', -1)) != 0:
            return jsonify({'mensagem': {'informacao': 'Acesso exclusivo para administradores.', 'tipo': 'erro'}}), 403

        con = conectar_banco()
        cursor = con.cursor()

        tipo = request.args.get('tipo')

        if tipo is not None:

            tipo = int(tipo)

            cursor.execute("""
                SELECT ID_USUARIO, NOME, EMAIL, TELEFONE, TIPO, ATIVO,
                       COALESCE(JA_BLOQUEADO, 0)
                FROM USUARIO
                WHERE TIPO = ?
                ORDER BY ID_USUARIO
            """, (tipo,))

        else:

            cursor.execute("""
                SELECT ID_USUARIO, NOME, EMAIL, TELEFONE, TIPO, ATIVO,
                       COALESCE(JA_BLOQUEADO, 0)
                FROM USUARIO
                ORDER BY ID_USUARIO
            """)

        usuarios = cursor.fetchall()

        resultado = []

        for usuario in usuarios:

            if usuario[4] == 0:
                tipo_nome = 'ADM'

            elif usuario[4] == 1:
                tipo_nome = 'Usuário'

            elif usuario[4] == 2:
                tipo_nome = 'Barbeiro'

            else:
                tipo_nome = 'Desconhecido'

            # Histórico de bloqueio: ATIVO = 2 (bloqueio por tentativas de
            # login) ou JA_BLOQUEADO = 1 (desativado pelo menos uma vez
            # pela administração). Assim, a primeira ativação mostra
            # "Ativar" e as seguintes mostram "Reativar".
            ja_foi_bloqueado = (
                int(usuario[5] or 0) == 2
                or int(usuario[6] or 0) == 1
            )

            resultado.append({
                'id': usuario[0],
                'nome': usuario[1],
                'email': usuario[2],
                'telefone': usuario[3],
                'tipo': usuario[4],
                'tipo_nome': tipo_nome,
                'ativo': int(usuario[5] or 0) == 1,
                'ja_foi_bloqueado': ja_foi_bloqueado,
                'foto_perfil': buscar_foto_perfil(usuario[0])
            })

        return jsonify(resultado), 200

    except Exception as erro:

        return jsonify({
            'mensagem': {'informacao': str(erro), 'tipo': 'erro'}
        }), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


# ==========================================================
# ATIVAR / DESATIVAR USUÁRIO (SOMENTE ADMIN)
# ==========================================================
# Ao desativar, o motivo é obrigatório e o e-mail é enviado antes de
# persistir a mudança. Assim, uma falha no e-mail não bloqueia o usuário
# sem que ele seja comunicado.

@app.route('/usuarios/<int:id_usuario>/status', methods=['PUT'])
def alterar_status_usuario(id_usuario):
    con = None
    cursor = None
    try:
        token = decodificar_token()
        if not token or int(token.get('tipo', -1)) != 0:
            return jsonify({'mensagem': {'informacao': 'Acesso exclusivo para administradores.', 'tipo': 'erro'}}), 403

        dados = request.get_json(silent=True) or {}
        ativo = dados.get('ativo')
        motivo = str(dados.get('motivo') or '').strip()
        if not isinstance(ativo, bool):
            return jsonify({'mensagem': {'informacao': 'Informe o novo status do usuário.', 'tipo': 'erro'}}), 400
        if not ativo and not motivo:
            return jsonify({'mensagem': {'informacao': 'O motivo da desativação é obrigatório.', 'tipo': 'erro'}}), 400

        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute('SELECT NOME, EMAIL, ATIVO, COALESCE(JA_BLOQUEADO, 0) FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
        usuario = cursor.fetchone()
        if not usuario:
            return jsonify({'mensagem': {'informacao': 'Usuário não encontrado.', 'tipo': 'erro'}}), 404

        nome, email, status_atual, ja_bloqueado = usuario
        novo_status = 1 if ativo else 0
        if int(status_atual or 0) == novo_status:
            return jsonify({'mensagem': {'informacao': 'O usuário já está com esse status.', 'tipo': 'aviso'}}), 200

        if not ativo:
            email_enviado = enviando_email(
                destinatario=email,
                assunto='Acesso desativado - Cortaê',
                mensagem='Seu acesso à plataforma foi desativado.',
                codigo='—',
                nome=nome,
                mensagem_secundaria=f'Motivo informado pela administração: {motivo}'
            )
            if not email_enviado:
                return jsonify({'mensagem': {'informacao': 'Não foi possível enviar o e-mail. O usuário não foi desativado.', 'tipo': 'erro'}}), 502

        # Ao desativar, marca o histórico de bloqueio (JA_BLOQUEADO = 1)
        # para que a próxima ativação seja exibida como "Reativar".
        if novo_status == 0:
            cursor.execute("""
                UPDATE USUARIO
                SET ATIVO = ?,
                    TENTATIVA = 0,
                    EMAIL_CONFIRMADO = 1,
                    JA_BLOQUEADO = 1
                WHERE ID_USUARIO = ?
            """, (novo_status, id_usuario))
        else:
            # Mantém o histórico de bloqueio: o campo JA_BLOQUEADO só
            # assume 1 (nunca volta a 0). Assim, quem já foi desativado
            # ou bloqueado por tentativas de login (ATIVO = 2) continua
            # marcado como "já foi bloqueado" e a ação aparece como
            # "Reativar"; quem nunca foi bloqueado mantém 0 e aparece
            # como "Ativar".
            cursor.execute("""
                UPDATE USUARIO
                SET ATIVO = ?,
                    TENTATIVA = 0,
                    EMAIL_CONFIRMADO = 1,
                    JA_BLOQUEADO = CASE WHEN ? = 2 THEN 1
                                        ELSE COALESCE(JA_BLOQUEADO, 0) END
                WHERE ID_USUARIO = ?
            """, (novo_status, int(status_atual or 0), id_usuario))
        con.commit()
        ja_foi_bloqueado_final = bool(
            not ativo
            or int(status_atual or 0) == 2
            or int(ja_bloqueado or 0) == 1
        )
        return jsonify({'mensagem': {'informacao': 'Usuário ativado com sucesso.' if ativo else 'Usuário desativado e comunicado por e-mail.', 'tipo': 'sucesso'}, 'ativo': ativo, 'ja_foi_bloqueado': ja_foi_bloqueado_final}), 200
    except Exception as erro:
        if con:
            con.rollback()
        return jsonify({'mensagem': {'informacao': 'Erro ao alterar status do usuário.', 'tipo': 'erro'}, 'detalhes': str(erro)}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()
