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
@app.route('/tabela/<int:torneio_id>')
def tabela(torneio_id=None):
    torneio = None
    competidores = []

    if torneio_id:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM torneios WHERE id = %s", (torneio_id,))
        torneio = cursor.fetchone()

        # Busca a classificação pronta direto da View com DENSE_RANK()
        cursor.execute(
            "SELECT * FROM vw_classificacao_geral WHERE torneio_id = %s ORDER BY posicao_ranking ASC",
            (torneio_id,)
        )
        competidores = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template('tabela.html', torneio=torneio, competidores=competidores)


@app.route('/editar-tabela')
@app.route('/editar-tabela/<int:torneio_id>')
def editar_tabela(torneio_id=None):
    if 'usuario' not in session:
        return redirect(url_for('auth'))

    torneio = None
    competidores = []

    if torneio_id:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM torneios WHERE id = %s AND usuario_id = %s",
            (torneio_id, session['usuario']['id'])
        )
        torneio = cursor.fetchone()

        if torneio:
            cursor.execute(
                "SELECT * FROM vw_classificacao_geral WHERE torneio_id = %s ORDER BY posicao_ranking ASC",
                (torneio_id,)
            )
            competidores = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template('editar_tabela.html', torneio=torneio, competidores=competidores)


@app.route('/salvar-torneio', methods=['POST'])
def salvar_torneio():
    if 'usuario' not in session:
        return redirect(url_for('auth'))

    torneio_id = request.form.get('torneio_id')
    nome = request.form.get('nome', '').strip() or 'Novo Campeonato'
    modalidade = request.form.get('modalidade', 'futebol')
    temporada = request.form.get('temporada', '').strip()
    formato = request.form.get('formato', 'pontos_corridos')
    qtd_participantes = int(request.form.get('qtd_participantes') or 20)
    cor_principal = request.form.get('cor_principal', '#2F5E49')
    cor_destaque = request.form.get('cor_destaque', '#78B89A')
    cor_classificacao = request.form.get('cor_classificacao', '#237A57')
    cor_rebaixamento = request.form.get('cor_rebaixamento', '#B84A4A')

    conn = get_db_connection()
    cursor = conn.cursor()

    if torneio_id:
        cursor.execute("""
            UPDATE torneios
               SET nome = %s, modalidade = %s, temporada = %s, formato = %s,
                   qtd_participantes = %s, cor_principal = %s, cor_destaque = %s,
                   cor_classificacao = %s, cor_rebaixamento = %s
             WHERE id = %s AND usuario_id = %s
        """, (nome, modalidade, temporada, formato, qtd_participantes,
              cor_principal, cor_destaque, cor_classificacao, cor_rebaixamento,
              torneio_id, session['usuario']['id']))
        conn.commit()
    else:
        cursor.execute("""
            INSERT INTO torneios (
                usuario_id, nome, modalidade, temporada, formato, qtd_participantes,
                cor_principal, cor_destaque, cor_classificacao, cor_rebaixamento
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (session['usuario']['id'], nome, modalidade, temporada, formato, qtd_participantes,
              cor_principal, cor_destaque, cor_classificacao, cor_rebaixamento))
        conn.commit()
        torneio_id = cursor.lastrowid

    cursor.close()
    conn.close()
    return redirect(url_for('editar_tabela', torneio_id=torneio_id))


@app.route('/adicionar-participante/<int:torneio_id>', methods=['POST'])
def adicionar_participante(torneio_id):
    if 'usuario' not in session:
        return redirect(url_for('auth'))

    nome = request.form.get('nome_participante', '').strip()
    sigla = request.form.get('sigla', '').strip().upper() or None
    grupo = request.form.get('grupo', '').strip() or None

    if nome:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO participantes (torneio_id, nome, sigla, grupo)
            VALUES (%s, %s, %s, %s)
        """, (torneio_id, nome, sigla, grupo))
        conn.commit()
        cursor.close()
        conn.close()

    return redirect(url_for('editar_tabela', torneio_id=torneio_id))

@app.route('/registrar-partida/<int:torneio_id>', methods=['POST'])
def registrar_partida(torneio_id):
    if 'usuario' not in session:
        return redirect(url_for('auth'))

    rodada = int(request.form.get('rodada') or 1)
    data_hora = request.form.get('data_hora') or None
    status = request.form.get('status', 'finalizada')
    mandante_id = request.form.get('mandante_id')
    visitante_id = request.form.get('visitante_id')
    placar_mandante = int(request.form.get('placar_mandante') or 0)
    placar_visitante = int(request.form.get('placar_visitante') or 0)

    if mandante_id and visitante_id and mandante_id != visitante_id:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Cria a partida no calendário
        cursor.execute("""
            INSERT INTO partidas (torneio_id, rodada, data_hora, status)
            VALUES (%s, %s, %s, 'agendada')
        """, (torneio_id, rodada, data_hora))
        partida_id = cursor.lastrowid

        # 2. Se já tiver placar / finalizada, chama a Stored Procedure que calcula tudo no MySQL
        if status == 'finalizada':
            cursor.callproc('sp_registrar_confronto', [
                partida_id,
                int(mandante_id),
                int(visitante_id),
                placar_mandante,
                placar_visitante
            ])
        else:
            # Caso seja agendada/ao_vivo/adiada, apenas vincula os participantes e atualiza o status
            cursor.execute("""
                INSERT INTO resultados_partida (partida_id, participante_id, papel, pro, contra, pontos_obtidos, resultado)
                VALUES 
                    (%s, %s, 'mandante', %s, %s, 0, 'participacao'),
                    (%s, %s, 'visitante', %s, %s, 0, 'participacao')
            """, (partida_id, int(mandante_id), placar_mandante, placar_visitante,
                  partida_id, int(visitante_id), placar_visitante, placar_mandante))
            cursor.execute("UPDATE partidas SET status = %s WHERE id = %s", (status, partida_id))

        conn.commit()
        cursor.close()
        conn.close()

    return redirect(url_for('editar_tabela', torneio_id=torneio_id))

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