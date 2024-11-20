from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import bcrypt
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

app = Flask(__name__)
app.secret_key = '123456'
CORS(app, resources={r"/*": {"origins": "*"}})

# Configurações de sessão para persistência e segurança
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Impede acesso ao cookie via JavaScript
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Ajuste para Lax ou Strict, dependendo do comportamento desejado
app.config['SESSION_COOKIE_SECURE'] = False  # Desabilite em desenvolvimento, ative em produção com HTTPS
app.config['SESSION_PERMANENT'] = False  # Garante que a sessão será removida quando o navegador for fechado

def send_email(sender, password, recipient, subject, body, attachments=None):
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html'))

    if attachments:
        for attachment in attachments:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{attachment.filename}"',
            )
            msg.attach(part)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        return True, "E-mail enviado com sucesso."
    except Exception as e:
        return False, f"Erro ao enviar e-mail: {str(e)}"

@app.route('/index', methods=['GET'])
def render_index_page():
    return render_template('index.html')

@app.route('/enviar', methods=['POST'])
def handle_email():
    data = request.form
    sender = data.get('email-sender-bulk')
    password = data.get('email-password-bulk')
    subject = data.get('email-subject-bulk')
    body = data.get('email-body-hidden-bulk')

    file = request.files.get('csv-file')
    if not file:
        return jsonify({"message": "Arquivo CSV não foi fornecido."}), 400

    df = pd.read_csv(file)
    email_column = int(data.get('email-column'))

    attachments = []
    for key in request.files:
        if key.startswith('email-attachments'):
            attachment = request.files[key]
            if attachment:
                attachments.append(attachment)

    success, message = True, "Todos os e-mails foram enviados com sucesso."

    for i, row in df.iterrows():
        recipient = row[email_column]
        personalized_body = body
        for col_name in df.columns:
            personalized_body = personalized_body.replace(f'{{{col_name}}}', str(row[col_name]))

        email_success, email_message = send_email(sender, password, recipient, subject, personalized_body, attachments)
        if not email_success:
            success, message = False, email_message
            break

    return jsonify({"message": message})

def create_connection():
    connection = mysql.connector.connect(
        host='localhost',
        database='fast_send',
        user='root',
        password='0204Mis*'
    )
    return connection

@app.route('/register', methods=['POST'])
def register_user():
    data = request.form
    nome = data.get('username')
    senha = data.get('password')
    confirm_password = data.get('confirm-password')
    email = data.get('email')

    if senha != confirm_password:
        flash("As senhas não coincidem. Por favor, tente novamente.", "error")
        return redirect(url_for('render_register_page'))

    hashed_password = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())
    connection = create_connection()
    cursor = connection.cursor()

    try:
        sql = "INSERT INTO usuario (nome, senha, email) VALUES (%s, %s, %s)"
        cursor.execute(sql, (nome, hashed_password, email))
        connection.commit()
        flash("Usuário cadastrado com sucesso! <a href='/login'>Ir para Login</a>", "success")
        return redirect(url_for('render_register_page'))
    except Error as e:
        print(f"Ocorreu um erro: {e}")
        flash("Erro ao cadastrar usuário. Tente novamente.", "error")
        return redirect(url_for('render_register_page'))
    finally:
        cursor.close()
        connection.close()

@app.route('/register', methods=['GET'])
def render_register_page():
    return render_template('register.html')

@app.route('/login', methods=['GET'])
def render_login_page():
    print(f"ID da Sessão: {session.get('usuario_id')}")  # Verifica o valor da sessão
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_user():
    data = request.form
    email = data.get('email')
    senha = data.get('password').encode('utf-8')

    connection = create_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT id, senha FROM usuario WHERE email = %s", (email,))
        result = cursor.fetchone()

        if result and bcrypt.checkpw(senha, result[1].encode('utf-8')):  # Verificando senha
            session['usuario_id'] = result[0]  # Armazenando o usuario_id na sessão
            print(f"Usuário logado, ID: {session['usuario_id']}")  # Verificação de sessão
            return jsonify(success=True)
        else:
            return jsonify(success=False, message="E-mail ou senha inválidos.")
    except Error as e:
        print(f"Ocorreu um erro: {e}")
        return jsonify(success=False, message="Erro ao acessar o banco de dados.")
    finally:
        cursor.close()
        connection.close()

@app.route('/remetentes', methods=['POST'])
def cadastrar_remetente():
    # Verifique se o usuário está logado (por exemplo, usando a sessão)
    usuario_id = session.get('usuario_id')  # Obtendo o usuario_id da sessão

    if not usuario_id:
        return jsonify({"success": False, "message": "Você precisa estar logado para cadastrar um remetente."}), 403

    data = request.form
    email = data.get('email')
    senha_envio = data.get('senha_envio')

    if not email or not senha_envio:
        return jsonify({"success": False, "message": "E-mail e senha são obrigatórios."}), 400

    connection = create_connection()
    cursor = connection.cursor()

    try:
        # Passando o `usuario_id` para a inserção no banco de dados
        sql = "INSERT INTO remetentes (usuario_id, email, senha_envio) VALUES (%s, %s, %s)"
        cursor.execute(sql, (usuario_id, email, senha_envio))  # Adicionando o usuario_id
        connection.commit()
        return jsonify({"success": True, "message": "Remetente cadastrado com sucesso."}), 201
    except Error as e:
        print(f"Erro ao cadastrar remetente: {e}")
        return jsonify({"success": False, "message": "Erro ao cadastrar remetente."}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/remetentes', methods=['GET'])
def render_remetentes_page():
    if 'usuario_id' not in session:
        flash("Você precisa estar logado para acessar essa página.", "error")
        return redirect(url_for('render_login_page'))  # Redireciona para a página de login
    return render_template('remetentes.html')

@app.route('/remetentes/listar', methods=['GET'])
def listar_remetentes():
    usuario_id = session.get('usuario_id')

    if not usuario_id:
        flash("Você precisa estar logado para acessar essa página.", "error")
        return redirect(url_for('render_login_page'))  # Redireciona para a página de login
    
    connection = create_connection()
    cursor = connection.cursor()

    try:
        # Busca todos os remetentes cadastrados para o usuário logado
        cursor.execute("SELECT id, email FROM remetentes WHERE usuario_id = %s", (usuario_id,))
        remetentes = cursor.fetchall()

        return render_template('listar_remetentes.html', remetentes=remetentes)

    except Error as e:
        print(f"Erro ao listar remetentes: {e}")
        flash("Erro ao listar remetentes.", "error")
        return redirect(url_for('render_remetentes_page'))
    finally:
        cursor.close()
        connection.close()

@app.route('/remetentes/deletar/<int:id>', methods=['POST'])
def deletar_remetente(id):
    usuario_id = session.get('usuario_id')

    if not usuario_id:
        return jsonify({"success": False, "message": "Você precisa estar logado para deletar um remetente."}), 403

    connection = create_connection()
    cursor = connection.cursor()

    try:
        # Verifica se o remetente pertence ao usuário logado
        cursor.execute("SELECT id FROM remetentes WHERE id = %s AND usuario_id = %s", (id, usuario_id))
        remetente = cursor.fetchone()

        if remetente:
            # Deleta o remetente se ele existir
            cursor.execute("DELETE FROM remetentes WHERE id = %s", (id,))
            connection.commit()
            flash("Remetente deletado com sucesso.", "success")
            return redirect(url_for('render_remetentes_page'))  # Redireciona de volta para a página de listagem
        else:
            flash("Remetente não encontrado ou você não tem permissão para deletá-lo.", "error")
            return redirect(url_for('render_remetentes_page'))

    except Error as e:
        print(f"Erro ao deletar remetente: {e}")
        flash("Erro ao deletar remetente.", "error")
        return redirect(url_for('render_remetentes_page'))
    finally:
        cursor.close()
        connection.close()


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('usuario_id', None)  # Remove o usuário da sessão
    flash("Você foi deslogado com sucesso.", "success")
    return redirect(url_for('render_login_page'))  # Redireciona para a página de login

@app.route('/menu', methods=['GET'])
def render_menu_page():
    # Verifica se o usuário está logado
    if 'usuario_id' not in session:
        flash("Você precisa estar logado para acessar esta página.", "error")
        return redirect(url_for('render_login_page'))  # Redireciona para a página de login

    return render_template('menu.html')  # Renderiza a tela de menu

@app.route('/destinatarios', methods=['GET'])
def render_cadastrar_destinatario_page():
    if 'usuario_id' not in session:
        flash("Você precisa estar logado para acessar essa página.", "error")
        return redirect(url_for('render_login_page'))
    return render_template('cadastrar_destinatario.html')

@app.route('/destinatarios', methods=['POST'])
def cadastrar_destinatario():
    if 'usuario_id' not in session:
        return jsonify({"success": False, "message": "Você precisa estar logado para cadastrar um destinatário."}), 403

    data = request.form
    usuario_id = session.get('usuario_id')  # Obtém o usuário logado
    email = data.get('email')
    nome_empresa = data.get('nome_empresa')
    telefone = data.get('telefone')

    if not email or not nome_empresa:
        return jsonify({"success": False, "message": "E-mail e nome/empresa são obrigatórios."}), 400

    connection = create_connection()
    cursor = connection.cursor()

    try:
        # Insere o destinatário no banco de dados
        sql = """
        INSERT INTO destinatarios (usuario_id, email, nome_empresa, telefone)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (usuario_id, email, nome_empresa, telefone))
        connection.commit()
        flash("Destinatário cadastrado com sucesso!", "success")
        return redirect(url_for('render_cadastrar_destinatario_page'))
    except Error as e:
        print(f"Erro ao cadastrar destinatário: {e}")
        flash("Erro ao cadastrar destinatário. Tente novamente.", "error")
        return redirect(url_for('render_cadastrar_destinatario_page'))
    finally:
        cursor.close()
        connection.close()

@app.route('/destinatarios/listar', methods=['GET'])
def listar_destinatarios():
    usuario_id = session.get('usuario_id')

    if not usuario_id:
        flash("Você precisa estar logado para acessar essa página.", "error")
        return redirect(url_for('render_login_page'))  # Redireciona para a página de login
    
    connection = create_connection()
    cursor = connection.cursor()

    try:
        # Busca todos os destinatários cadastrados para o usuário logado
        cursor.execute("SELECT id, email, nome_empresa, telefone FROM destinatarios WHERE usuario_id = %s", (usuario_id,))
        destinatarios = cursor.fetchall()

        return render_template('listar_destinatarios.html', remetentes=destinatarios)

    except Error as e:
        print(f"Erro ao listar destinatários: {e}")
        flash("Erro ao listar destinatários.", "error")
        return redirect(url_for('render_remetentes_page'))
    finally:
        cursor.close()
        connection.close()

@app.route('/destinatarios/deletar/<int:id>', methods=['POST'])
def deletar_destinatario(id):
    usuario_id = session.get('usuario_id')

    if not usuario_id:
        flash("Você precisa estar logado para acessar essa página.", "error")
        return redirect(url_for('render_login_page'))  # Redireciona para a página de login

    connection = create_connection()
    cursor = connection.cursor()

    try:
        # Deleta o destinatário com o id fornecido
        cursor.execute("DELETE FROM destinatarios WHERE id = %s AND usuario_id = %s", (id, usuario_id))
        connection.commit()

        flash("Destinatário deletado com sucesso!", "success")
        return redirect(url_for('listar_destinatarios'))  # Redireciona de volta para a lista

    except Error as e:
        print(f"Erro ao deletar destinatário: {e}")
        flash("Erro ao deletar destinatário.", "error")
        return redirect(url_for('listar_destinatarios'))
    finally:
        cursor.close()
        connection.close()

@app.route('/envio_email', methods=['GET'])
def render_envio_email_page():
    usuario_id = session.get('usuario_id')
    
    if not usuario_id:
        flash("Você precisa estar logado para acessar esta página.", "error")
        return redirect(url_for('render_login_page'))  # Redireciona para a página de login

    # Carregar remetentes e destinatários do banco de dados
    connection = create_connection()
    cursor = connection.cursor()

    try:
        # Buscar remetentes
        cursor.execute("SELECT id, email FROM remetentes WHERE usuario_id = %s", (usuario_id,))
        remetentes = cursor.fetchall()

        # Buscar destinatários
        cursor.execute("SELECT id, email, nome_empresa FROM destinatarios WHERE usuario_id = %s", (usuario_id,))
        destinatarios = cursor.fetchall()

        return render_template('envio_email.html', remetentes=remetentes, destinatarios=destinatarios)

    except Error as e:
        print(f"Erro ao carregar remetentes e destinatários: {e}")
        flash("Erro ao carregar remetentes e destinatários.", "error")
        return redirect(url_for('render_menu_page'))  # Retorna ao menu em caso de erro
    finally:
        cursor.close()
        connection.close()


@app.route('/enviar_email', methods=['POST'])
def enviar_email():
    data = request.form
    remetente_id = data.get('remetente')
    destinatarios_ids = data.getlist('destinatarios')  # Lista de IDs dos destinatários selecionados
    assunto = data.get('assunto')
    corpo = data.get('corpo_email')
    
    if not remetente_id or not destinatarios_ids or not assunto or not corpo:
        flash("Por favor, preencha todos os campos.", "error")
        return redirect(url_for('render_envio_email_page'))

    # Carregar informações do remetente
    connection = create_connection()
    cursor = connection.cursor()
    
    try:
        cursor.execute("SELECT email, senha_envio FROM remetentes WHERE id = %s", (remetente_id,))
        remetente = cursor.fetchone()
        if not remetente:
            flash("Remetente não encontrado.", "error")
            return redirect(url_for('render_envio_email_page'))

        remetente_email, remetente_senha = remetente

        # Enviar email para cada destinatário
        for destinatario_id in destinatarios_ids:
            cursor.execute("SELECT email FROM destinatarios WHERE id = %s", (destinatario_id,))
            destinatario = cursor.fetchone()
            if destinatario:
                destinatario_email = destinatario[0]
                # Chame a função `send_email` para enviar o email
                success, message = send_email(remetente_email, remetente_senha, destinatario_email, assunto, corpo)
                if not success:
                    flash(message, "error")
                    return redirect(url_for('render_envio_email_page'))

        flash("E-mails enviados com sucesso!", "success")
        return redirect(url_for('render_envio_email_page'))

    except Error as e:
        print(f"Erro ao enviar email: {e}")
        flash("Erro ao enviar e-mails.", "error")
        return redirect(url_for('render_envio_email_page'))
    finally:
        cursor.close()
        connection.close()



if __name__ == '__main__':
    app.run(debug=True)
