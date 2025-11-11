from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import folium
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_super_segura'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gerencia.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ===== MODELOS =====
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', backref=db.backref('entries', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ===== RUTAS =====

@app.route('/')
@login_required
def index():
    entries = Entry.query.order_by(Entry.created_at.desc()).all()
    return render_template('public_entries.html', entries=entries)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Verificar si el usuario ya existe
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe.')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registro exitoso. Ya puedes iniciar sesión.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Bienvenido, ' + user.username)
            return redirect(url_for('dashboard') if user.is_admin else url_for('index'))
        else:
            flash('Credenciales inválidas.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.')
    return redirect(url_for('index'))

@app.route('/create_entry', methods=['GET', 'POST'])
@login_required
def create_entry():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        new_entry = Entry(title=title, description=description, author=current_user)
        db.session.add(new_entry)
        db.session.commit()
        flash('Entrada creada correctamente.')
        return redirect(url_for('dashboard' if current_user.is_admin else 'my_entries'))

    return render_template('create_entry.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Acceso denegado.')
        return redirect(url_for('index'))
    entries = Entry.query.order_by(Entry.created_at.desc()).all()
    return render_template('dashboard.html', entries=entries)

@app.route('/my_entries')
@login_required
def my_entries():
    # Solo el usuario normal verá sus formularios
    if current_user.is_admin:
        return redirect(url_for('dashboard'))
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.created_at.desc()).all()
    return render_template('my_entries.html', entries=entries)

@app.route('/mapa')
@login_required
def mapa():
    if current_user.is_admin:
        flash('El administrador no tiene acceso al mapa de usuarios.')
        return redirect(url_for('dashboard'))

    # Crea un mapa base centrado en Colombia (por ejemplo)
    latitud = 4.7110
    longitud = -74.0721
    mapa_alerta = folium.Map(location=[latitud, longitud], zoom_start=10)

    mapa_path = os.path.join('static', 'mapa_alerta.html')
    mapa_alerta.save(mapa_path)

    return render_template('mapa.html', mapa_path=mapa_path)


@app.route('/alerta', methods=['POST'])
@login_required
def alerta():
    data = request.get_json()
    lat = data.get('lat')
    lon = data.get('lon')

    # Crear un mapa centrado en la ubicación del usuario
    mapa_alerta = folium.Map(location=[lat, lon], zoom_start=14)

    folium.Marker(
        location=[lat, lon],
        popup=f'🚨 Alerta de {current_user.username}',
        tooltip='Ubicación actual',
        icon=folium.Icon(color='red', icon='exclamation-sign')
    ).add_to(mapa_alerta)

    mapa_path = os.path.join('static', 'mapa_alerta.html')
    mapa_alerta.save(mapa_path)

    return {'status': 'ok'}


# ===== Inicialización =====
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Crear admin si no existe
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'), is_admin=True)
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)
