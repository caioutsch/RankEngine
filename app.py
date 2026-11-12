import os
from flask import Flask, render_template, session, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from db import get_db_connection

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'rankengine_dev_secret_key')

def gerar_iniciais(nome):
    partes = nome.strip().split()
    if len(partes) > 1:
        return (partes[0][0] + partes[-1][0]).upper()
    return nome[:2].upper()

@app.context_processor
def inject_user():
    return dict(usuario=session.get('usuario'))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/tabela')
def tabela():
    competidores = []
    return render_template('tabela.html', competidores=competidores)

@app.route('/editar-tabela')
def editar_tabela():
    competidores = []
    return render_template('editar_tabela.html', competidores=competidores)

@app.route('/minhas-tabelas')
def minhas_tabelas():
    if 'usuario' not in session:
        return redirect(url_for('auth'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM torneios WHERE usuario_id = %s ORDER BY atualizado_em DESC",
        (session['usuario']['id'],)
    )
    tabelas_salvas = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('minhas_tabelas.html', tabelas=tabelas_salvas)

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        acao = request.form.get('acao', 'login')
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            if acao == 'register':
                nome = request.form.get('nome', '').strip()
                cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
                if cursor.fetchone():
                    cursor.close()
                    conn.close()
                    return render_template('auth.html', erro="Este e-mail já está cadastrado.")

                senha_hash = generate_password_hash(senha)
                cursor.execute(
                    "INSERT INTO usuarios (nome, email, senha_hash) VALUES (%s, %s, %s)",
                    (nome, email, senha_hash)
                )
                conn.commit()
                user_id = cursor.lastrowid

                session['usuario'] = {
                    'id': user_id,
                    'nome': nome,
                    'email': email,
                    'iniciais': gerar_iniciais(nome)
                }
                cursor.close()
                conn.close()
                return redirect(url_for('perfil'))

            else:
                cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
                user = cursor.fetchone()
                cursor.close()
                conn.close()

                if user and check_password_hash(user['senha_hash'], senha):
                    session['usuario'] = {
                        'id': user['id'],
                        'nome': user['nome'],
                        'email': user['email'],
                        'iniciais': gerar_iniciais(user['nome'])
                    }
                    return redirect(url_for('perfil'))
                else:
                    return render_template('auth.html', erro="E-mail ou senha incorretos.")

        except Exception as e:
            return render_template('auth.html', erro=f"Erro no banco de dados: {e}")

    return render_template('auth.html')

@app.route('/perfil')
def perfil():
    if 'usuario' not in session:
        return redirect(url_for('auth'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM torneios WHERE usuario_id = %s ORDER BY atualizado_em DESC",
        (session['usuario']['id'],)
    )
    tabelas_salvas = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('perfil.html', tabelas=tabelas_salvas)

@app.route('/atualizar-perfil', methods=['POST'])
def atualizar_perfil():
    if 'usuario' not in session:
        return redirect(url_for('auth'))

    novo_nome = request.form.get('novo_nome', '').strip()
    if novo_nome:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE usuarios SET nome = %s WHERE id = %s",
            (novo_nome, session['usuario']['id'])
        )
        conn.commit()
        cursor.close()
        conn.close()

        usuario = session['usuario']
        usuario['nome'] = novo_nome
        usuario['iniciais'] = gerar_iniciais(novo_nome)
        session['usuario'] = usuario
        session.modified = True

    return redirect(url_for('perfil'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)