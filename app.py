from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
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
app.secret_key = 'sua_chave_secreta_aqui'
CORS(app, resources={r"/*": {"origins": "*"}})

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

@app.route('/', methods=['POST'])
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
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_user():
    data = request.form
    email = data.get('email')
    senha = data.get('password').encode('utf-8')

    connection = create_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT senha FROM usuario WHERE email = %s", (email,))
        result = cursor.fetchone()

        if result and bcrypt.checkpw(senha, result[0].encode('utf-8')):
            return jsonify(success=True)
        else:
            return jsonify(success=False, message="E-mail ou senha inválidos.")
    except Error as e:
        print(f"Ocorreu um erro: {e}")
        return jsonify(success=False, message="Erro ao acessar o banco de dados.")
    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    app.run(debug=True)
