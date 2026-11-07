from flask import Flask, render_template, redirect, url_for, flash, session, request
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import database
import sqlite3
import os
from flask_wtf.csrf import CSRFProtect


app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']

app.config['SESSION_COOKIE_SECURE'] = (
    os.environ.get('SECURE_COOKIES') == 'true'
)

csrf = CSRFProtect(app)

database.inicijaliziraj_bazu()

def racun_trajanja(pocetak, kraj):
    if kraj < pocetak:
        raise ValueError("Kraj smjene ne moze biti prije pocetka!")

    sekunde = (kraj - pocetak).total_seconds()
    minute = int((sekunde % 3600) // 60)
    sati = int(sekunde // 3600)
    return sati, minute

# Main page
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = database.dohvati_korisnika_po_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for('login'))
    username = user[1]
    poc_ispis = ''
    kraj_ispis = ''
    sati = None
    minute = None
    zavrsena = session.pop('zavrsena_smjena', None)
    if zavrsena is not None:
        poc_ispis = zavrsena['pocetak']
        kraj_ispis = zavrsena['kraj']
        sati = zavrsena['sati']
        minute = zavrsena['minute']
    else:
        aktivna = database.dohvati_aktivnu_smjenu(user_id)
        if aktivna is not None:
            pocetak = datetime.fromisoformat(aktivna[1])
            pocetak_lokalno = pocetak.astimezone(ZoneInfo(aktivna[5]))
            poc_ispis = pocetak_lokalno.strftime('%H:%M')
    return render_template('index.html', pocetak=poc_ispis, kraj=kraj_ispis, sati=sati, minute=minute, user=username)

# Register the user
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if username and password:
            password_hash = generate_password_hash(password)
            try:
                database.spremi_korisnika(username, password_hash)
            except sqlite3.IntegrityError:
                flash("Korisničko ime već postoji!")
            else:
                return redirect(url_for('login'))
        else:
            flash("Nedostaju korisničko ime ili lozinka!")
    return render_template('register.html')

# Login into account
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        username = request.form['username'].strip()
        password = request.form['password']
        user = database.dohvati_korisnika(username)
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            return redirect(url_for('index'))
        flash("Pogrešno korisničko ime ili lozinka!")
    return render_template('login.html')

# Log out of the account
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

# Register starting time
@app.route('/start', methods=['POST'])
def start_shift():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    timezone_name = request.form.get('timezone')
    if not timezone_name:
        flash("Nema vremenske zone!")
        return redirect(url_for('index'))
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        flash("Neispravna vremenska zona!")
        return redirect(url_for('index'))

    user_id = session['user_id']
    aktivna = database.dohvati_aktivnu_smjenu(user_id)
    if aktivna is None:
        pocetak = datetime.now(timezone.utc)
        database.spremi_pocetak_smjene(pocetak, user_id, timezone_name)
    else:
        flash("Smjena je već pocela!")
    return redirect(url_for('index'))

# Register ending time
@app.route('/end', methods=['POST'])
def end_shift():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    aktivna = database.dohvati_aktivnu_smjenu(user_id)
    if aktivna is None:
        flash('Nema aktivne smjene!')
    else:
        id_smjene = aktivna[0]
        kraj = datetime.now(timezone.utc)
        database.spremi_kraj_smjene(id_smjene, kraj, user_id)
        pocetak = datetime.fromisoformat(aktivna[1])
        sati, minute = racun_trajanja(pocetak, kraj)
        pocetak_lokalno = pocetak.astimezone(ZoneInfo(aktivna[5]))
        kraj_lokalno = kraj.astimezone(ZoneInfo(aktivna[5]))
        session['zavrsena_smjena'] = {
            'pocetak': pocetak_lokalno.strftime('%H:%M'),
            'kraj': kraj_lokalno.strftime('%H:%M'),
            'sati': sati,
            'minute': minute
        }
    return redirect(url_for('index'))

# Creating history
@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    zavrsene_smjene = database.dohvati_zavrsene_smjene(user_id)
    smjene_za_prikaz = []
    dani = [
        'Ponedjeljak',
        'Utorak',
        'Srijeda',
        'Četvrtak',
        'Petak',
        'Subota',
        'Nedjelja'
    ]
    for smjena in zavrsene_smjene:
        pocetak = datetime.fromisoformat(smjena[1])
        kraj = datetime.fromisoformat(smjena[2])
        sati, minute = racun_trajanja(pocetak, kraj)
        pocetak_lokalno = pocetak.astimezone(ZoneInfo(smjena[5]))
        dan = dani[pocetak_lokalno.weekday()]
        kraj_lokalno = kraj.astimezone(ZoneInfo(smjena[5]))
        dan_kraja = dani[kraj_lokalno.weekday()]
        jedna_za_prikaz = {
            'id': smjena[0],
            'dan': dan,
            'datum': pocetak_lokalno.strftime('%d.%m.%Y.'),
            'pocetak': pocetak_lokalno.strftime('%H:%M'),
            'kraj': kraj_lokalno.strftime('%H:%M'),
            'isti_dan': pocetak_lokalno.date() == kraj_lokalno.date(),
            'datum_kraja': kraj_lokalno.strftime('%d.%m.%Y.'),
            'dan_kraja': dan_kraja,
            'sati': sati,
            'minute': minute,
            'biljeska': smjena[3]
        }
        smjene_za_prikaz.append(jedna_za_prikaz)
    return render_template('history.html', smjene=smjene_za_prikaz)

# Zapis biljeske u bazu
@app.route('/history/<int:id_smjene>/note', methods=['POST'])
def spremi_note(id_smjene):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    biljeska = request.form.get('biljeska', '').strip()
    try:
        database.spremi_biljesku(id_smjene, biljeska, user_id)
    except ValueError:
        flash('Smjena ne postoji ili joj nemaš pristup.')
    else:
        flash('Bilješka je spremljena.')
    return redirect(url_for('history'))


if __name__ == '__main__':
    app.run(debug=os.environ.get('DEBUG') == 'true',
            host='0.0.0.0',
            port=5000)

