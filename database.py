import sqlite3
from contextlib import closing
import os


dir_path = os.path.dirname(__file__)
DATABASE = os.path.join(dir_path, 'shifttracker.db')


# Funkcija spajanja na bazu podataka
def spoji_na_bazu():
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# Inicijalizacija baze podataka za spremanje svih smjena i korisnika
def inicijaliziraj_bazu():
    with closing(spoji_na_bazu()) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, 
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS smjene (
                    id INTEGER PRIMARY KEY, 
                    pocetak TEXT NOT NULL, 
                    kraj TEXT, 
                    biljeska TEXT,
                    user_id INTEGER NOT NULL,
                    timezone TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

# Spremanje korisnika
def spremi_korisnika(username, password_hash):
    with closing(spoji_na_bazu()) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash)
            )
            user_id = cursor.lastrowid
    return user_id

# Dohvacanje korisnika
def dohvati_korisnika(username):
    with closing(spoji_na_bazu()) as conn:
        cursor = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)            )
        user = cursor.fetchone()
    return user

def dohvati_korisnika_po_id(user_id):
    with closing(spoji_na_bazu()) as conn:
        cursor = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        )
        user = cursor.fetchone()
    return user

# Spremanje pocetka smjene u bazu
def spremi_pocetak_smjene(pocetak, user_id, timezone_name):
    format_pocetak = pocetak.isoformat()
    with closing(spoji_na_bazu()) as conn:
        with conn:
            conn.execute(
                "INSERT INTO smjene (pocetak, user_id, timezone) VALUES (?, ?, ?)",
                (format_pocetak, user_id, timezone_name)
            )

# Spremanje kraja smjene u bazu
def spremi_kraj_smjene(id_smjene, kraj, user_id):
    format_kraj = kraj.isoformat()
    with closing(spoji_na_bazu()) as conn:
        with conn:
            cursor = conn.execute(
                "UPDATE smjene SET kraj = ? WHERE id = ? AND user_id = ?",
                (format_kraj, id_smjene, user_id)
            )
            if cursor.rowcount == 0:
                raise ValueError("Smjena ne postoji ili ne pripada korisniku!")

# Spremanje biljeske u bazu
def spremi_biljesku(id_smjene, biljeska, user_id):
    with closing(spoji_na_bazu()) as conn:
        with conn:
            cursor = conn.execute(
                "UPDATE smjene SET biljeska = ? WHERE id = ? AND user_id = ?",
                (biljeska, id_smjene, user_id)
            )
            if cursor.rowcount == 0:
                raise ValueError("Smjena ne postoji ili ne pripada korisniku!")

# Dohvacanje aktivne smjene (ona koja ima samo pocetak), ukoliko postoji
def dohvati_aktivnu_smjenu(user_id):
    with closing(spoji_na_bazu()) as conn:
        cursor = conn.execute(
            "SELECT * FROM smjene WHERE kraj IS NULL AND user_id = ?",
            (user_id,)
        )
        aktivne = cursor.fetchall()
    if not aktivne:
        return None
    elif len(aktivne) == 1:
        return aktivne[0]
    else:
        raise ValueError("Postoji vise aktivnih smjena!")

# Dohvacanje svih proslih smjena
def dohvati_zavrsene_smjene(user_id):
    with closing(spoji_na_bazu()) as conn:
        cursor = conn.execute("""
        SELECT * FROM smjene
        WHERE kraj IS NOT NULL AND user_id = ?
        ORDER BY pocetak DESC """,
        (user_id,)
        )
        zavrsene = cursor.fetchall()
    return zavrsene
