from flask import Flask, render_template, session, redirect, url_for, request

app = Flask(__name__)
app.secret_key = 'rankengine_dev_secret_key'  # Necessário para usar session no Flask

# Context processor: injeta 'usuario' automaticamente em TODOS os templates HTML
@app.context_processor
def inject_user():
    return dict(usuario=session.get('usuario'))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/tabela')
def tabela():
    # Passa uma lista vazia de competidores (sem dados aleatórios)
    competidores = session.get('tabela_atual', [])
    return render_template('tabela.html', competidores=competidores)

@app.route('/editar-tabela')
def editar_tabela():
    competidores = session.get('tabela_atual', [])
    return render_template('editar_tabela.html', competidores=competidores)

@app.route('/minhas-tabelas')
def minhas_tabelas():
    # Proteção: se não estiver logado, redireciona para login/cadastro
    if 'usuario' not in session:
        return redirect(url_for('auth'))
    
    tabelas_salvas = session.get('tabelas_salvas', [])
    return render_template('minhas_tabelas.html', tabelas=tabelas_salvas)

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        # Captura o nome digitado no cadastro ou extrai do e-mail no login
        nome = request.form.get('nome')
        email = request.form.get('email', '')
        
        if not nome and email:
            nome = email.split('@')[0].capitalize()
        elif not nome:
            nome = 'Usuário'

        # Gera iniciais para o avatar (ex: "Caio Utsch" -> "CU")
        partes = nome.strip().split()
        iniciais = (partes[0][0] + partes[-1][0]).upper() if len(partes) > 1 else nome[:2].upper()

        session['usuario'] = {
            'nome': nome,
            'email': email,
            'iniciais': iniciais
        }
        # Inicializa listas reais vazias para o usuário novo
        session.setdefault('tabelas_salvas', [])
        return redirect(url_for('perfil'))

    return render_template('auth.html')

@app.route('/perfil')
def perfil():
    if 'usuario' not in session:
        return redirect(url_for('auth'))
    
    tabelas_salvas = session.get('tabelas_salvas', [])
    return render_template('perfil.html', tabelas=tabelas_salvas)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)