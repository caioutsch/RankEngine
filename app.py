from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/tabela')
def tabela():
    return render_template('tabela.html')

@app.route('/editar-tabela')
def editar_tabela():
    return render_template('editar_tabela.html')

if __name__ == '__main__':
    app.run(debug=True)