from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
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

if __name__ == '__main__':
    app.run(debug=True)
