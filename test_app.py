from http.client import responses
from zoneinfo import ZoneInfo

from werkzeug.security import check_password_hash, generate_password_hash
from app import app
import pytest
from app import racun_trajanja
from datetime import datetime, timezone
import database


def test_racun_trajanja():
    pocetak = datetime(2026, 9, 19, 12, 0)
    kraj = datetime(2026, 9, 19, 18, 0)
    sati, minute = racun_trajanja(pocetak, kraj)
    assert sati == 6
    assert minute == 0

def test_manje_od_sata():
    pocetak = datetime(2026, 9, 19, 3, 15)
    kraj = datetime(2026, 9, 19, 3, 22)
    sati, minute = racun_trajanja(pocetak, kraj)
    assert sati == 0
    assert minute == 7

def test_kraj_prije_pocetka():
    pocetak = datetime(2026, 9, 19, 3, 15)
    kraj = datetime(2026, 9, 19, 0, 22)
    with pytest.raises(ValueError):
        racun_trajanja(pocetak, kraj)

def test_smjena_preko_ponoci():
    pocetak = datetime(2026, 9, 25, 22, 0)
    kraj = datetime(2026, 9, 26, 8, 0)
    sati, minute = racun_trajanja(pocetak, kraj)
    assert sati == 10
    assert minute == 0

# Pripremanje ciste baze za testiranje
@pytest.fixture
def test_database(tmp_path, monkeypatch):
    test_database = tmp_path / "test.db"
    monkeypatch.setattr(database, 'DATABASE', str(test_database))
    database.inicijaliziraj_bazu()

def test_zivotni_ciklus_smjene(test_database):
    pocetak = datetime(2026, 9, 25, 9, 10, tzinfo=timezone.utc)
    kraj = datetime(2026, 9, 25, 15, 10, tzinfo=timezone.utc)
    ena_id = database.spremi_korisnika('Ena', 'passEna')
    database.spremi_pocetak_smjene(pocetak, ena_id, timezone_name='Atlantic/Reykjavik')
    aktivna = database.dohvati_aktivnu_smjenu(ena_id)
    assert aktivna is not None
    assert aktivna[1] == pocetak.isoformat()
    database.spremi_kraj_smjene(aktivna[0], kraj, ena_id)
    zavrsene = database.dohvati_zavrsene_smjene(ena_id)
    zadnja = zavrsene[0]
    aktivna = database.dohvati_aktivnu_smjenu(ena_id)
    assert aktivna is None
    assert len(zavrsene) == 1
    assert zadnja[1] == pocetak.isoformat()
    assert zadnja[2] == kraj.isoformat()

def test_dohvati_zavrsene_smjene(test_database):
    pocetak = datetime(2026, 9, 25, 9, 10, tzinfo=timezone.utc)
    kraj = datetime(2026, 9, 25, 15, 10, tzinfo=timezone.utc)
    ena_id = database.spremi_korisnika('Ena', 'passEna')
    database.spremi_pocetak_smjene(pocetak, ena_id, timezone_name='Atlantic/Reykjavik')
    aktivna = database.dohvati_aktivnu_smjenu(ena_id)
    database.spremi_kraj_smjene(aktivna[0], kraj, ena_id)
    pocetak2 = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    database.spremi_pocetak_smjene(pocetak2, ena_id, timezone_name='Atlantic/Reykjavik')
    aktivna = database.dohvati_aktivnu_smjenu(ena_id)
    kraj2 = datetime(2026, 9, 23, 13, 0, tzinfo=timezone.utc)
    database.spremi_kraj_smjene(aktivna[0], kraj2, ena_id)

    zavrsene = database.dohvati_zavrsene_smjene(ena_id)
    assert len(zavrsene) == 2
    assert zavrsene[0][1] == pocetak.isoformat()
    assert zavrsene[0][2] == kraj.isoformat()
    assert zavrsene[1][1] == pocetak2.isoformat()
    assert zavrsene[1][2] == kraj2.isoformat()

def test_spremi_update_biljesku(test_database):
    pocetak = datetime(2026, 9, 25, 9, 10, tzinfo=timezone.utc)
    kraj = datetime(2026, 9, 25, 15, 10, tzinfo=timezone.utc)
    ena_id = database.spremi_korisnika('Ena', 'passEna')
    database.spremi_pocetak_smjene(pocetak, ena_id, timezone_name='Atlantic/Reykjavik')
    aktivna = database.dohvati_aktivnu_smjenu(ena_id)
    database.spremi_kraj_smjene(aktivna[0], kraj, ena_id)
    biljeska = 'Ovo je nova biljeska'
    database.spremi_biljesku(aktivna[0], biljeska, ena_id)
    zavrsene = database.dohvati_zavrsene_smjene(ena_id)
    zadnja = zavrsene[0]
    assert zadnja[3] == biljeska
    biljeska1 = 'Updateana biljeska'
    database.spremi_biljesku(aktivna[0], biljeska1, ena_id)
    zavrsene = database.dohvati_zavrsene_smjene(ena_id)
    zadnja = zavrsene[0]
    assert zadnja[3] == biljeska1

def test_multi_user(test_database):
    ena_id = database.spremi_korisnika('Ena', 'passEna')
    lu_id = database.spremi_korisnika('Lu', 'passLu')
    ena_pocetak = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
    database.spremi_pocetak_smjene(ena_pocetak, ena_id, timezone_name='Atlantic/Reykjavik')
    aktivna = database.dohvati_aktivnu_smjenu(ena_id)
    kraj = datetime(2026, 9, 25, 15, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        database.spremi_kraj_smjene(aktivna[0], kraj, lu_id)
    aktivna_nakon = database.dohvati_aktivnu_smjenu(ena_id)
    assert aktivna_nakon is not None

# priprema za testove
@pytest.fixture()
def client(test_database):
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as client:
        yield client


def test_index_bez_logina(client):
    response = client.get('/')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')

def test_histoy_bez_logina(client):
    response = client.get('/history')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')

def test_registracije(client):
    response = client.post(
        '/register',
        data={
            'username': 'ec',
            'password': 'bla'
        }
    )
    user = database.dohvati_korisnika('ec')
    assert user is not None
    assert user[1] == 'ec'
    assert check_password_hash(user[2], 'bla')
    assert response.headers['Location'].endswith('/login')

def test_login(client):
    password_hash = generate_password_hash('bla')
    user_id = database.spremi_korisnika('ec', password_hash)
    response = client.post(
        '/login',
        data={
            'username': 'ec',
            'password': 'bla'
        }
    )
    assert response.headers['Location'].endswith('/')
    assert response.status_code == 302

    with client.session_transaction() as session:
        assert session['user_id'] == user_id

def test_krivi_password(client):
    response = client.post(
        '/login',
        data={
            'username': 'ec',
            'password': 'jaja'
        }
    )
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert 'user_id' not in session
    html = response.get_data(as_text=True)
    assert 'Pogrešno korisničko ime ili lozinka!' in html

def test_logout(client):
    password_hash = generate_password_hash('jaja')
    database.spremi_korisnika('ec', password_hash)
    client.post(
        '/login',
        data={
            'username': 'ec',
            'password': 'jaja'
        }
    )
    with client.session_transaction() as session:
        assert 'user_id' in session

    response = client.post('/logout')
    with client.session_transaction() as session:
        assert 'user_id' not in session
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')

def test_multi_user_izolacija(client):
    password_hash_a = generate_password_hash('passA')
    user_a_id = database.spremi_korisnika('userA', password_hash_a)
    password_hash_b = generate_password_hash('passB')
    database.spremi_korisnika('userB', password_hash_b)
    database.spremi_pocetak_smjene(datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc), user_a_id, timezone_name='Atlantic/Reykjavik')
    aktivna = database.dohvati_aktivnu_smjenu(user_a_id)
    database.spremi_kraj_smjene(aktivna[0], datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc), user_a_id)
    client.post(
        '/login',
        data={
            'username': 'userB',
            'password': 'passB'
        }
    )
    response = client.get('/history')
    html = response.get_data(as_text=True)
    assert 'Nema završenih smjena!' in html
    client.post(
        '/login',
        data={
            'username': 'userA',
            'password': 'passA'
        }
    )
    response = client.get('/history')
    html = response.get_data(as_text=True)
    assert '09:00' in html
    assert '15:00' in html

def test_stale_session(client):
    with client.session_transaction() as session:
        session['user_id'] = 999
    response = client.get('/')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')
    with client.session_transaction() as session:
        assert 'user_id' not in session

def test_history_prikazuje_lokalno_vrijeme(client):
    pocetak = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)
    kraj = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)
    password_hash = generate_password_hash('passA')
    user_id = database.spremi_korisnika('userA', password_hash)
    database.spremi_pocetak_smjene(pocetak, user_id, timezone_name='Europe/Zagreb')
    aktivna = database.dohvati_aktivnu_smjenu(user_id)
    database.spremi_kraj_smjene(aktivna[0], kraj, user_id)
    with client.session_transaction() as session:
        session['user_id'] = user_id

    response = client.get('/history')
    html = response.get_data(as_text=True)
    assert '11:00' in html
    assert '12:00' in html

def test_invalid_timezone_not_start_shift(client):
    password_hash = generate_password_hash('passA')
    user_id = database.spremi_korisnika('userA', password_hash)
    with client.session_transaction() as session:
        session['user_id'] = user_id

    client.post('/start', data={'timezone': 'banana'})
    aktivna = database.dohvati_aktivnu_smjenu(user_id)
    assert aktivna is None

def test_missing_timezone(client):
    password_hash = generate_password_hash('passA')
    user_id = database.spremi_korisnika('userA', password_hash)
    with client.session_transaction() as session:
        session['user_id'] = user_id

    client.post('/start')
    aktivna = database.dohvati_aktivnu_smjenu(user_id)
    assert aktivna is None

def test_valid_timezone(client):
    password_hash = generate_password_hash('passA')
    user_id = database.spremi_korisnika('userA', password_hash)
    with client.session_transaction() as session:
        session['user_id'] = user_id

    client.post('/start', data={'timezone': 'Europe/Zagreb'})
    aktivna = database.dohvati_aktivnu_smjenu(user_id)
    assert aktivna is not None
    assert aktivna[5] == 'Europe/Zagreb'