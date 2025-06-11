from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# User model for authentication and roles
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user') # 'user' or 'montir'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

class Kerusakan(db.Model):
    __tablename__ = 'kerusakan'
    kerusakan_id = db.Column(db.String(5), primary_key=True)
    nama_kerusakan = db.Column(db.String(50), nullable=False)
    # Define cascade for deletion: if a Kerusakan is deleted, its related Solusi and AturanDiagnosis are also deleted
    solutions = db.relationship('Solusi', backref='kerusakan', lazy=True, cascade='all, delete-orphan')
    rules = db.relationship('AturanDiagnosis', backref='kerusakan', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Kerusakan {self.nama_kerusakan}>"

class Gejala(db.Model):
    __tablename__ = 'gejala'
    gejala_id = db.Column(db.String(5), primary_key=True)
    deskripsi_gejala = db.Column(db.Text, nullable=False)
    # Define cascade for deletion: if a Gejala is deleted, its related AturanDiagnosis are also deleted
    rules = db.relationship('AturanDiagnosis', backref='gejala', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Gejala {self.deskripsi_gejala}>"

class AturanDiagnosis(db.Model):
    __tablename__ = 'aturandiagnosis'
    aturan_id = db.Column(db.Integer, primary_key=True) # Will be auto-incremented
    kerusakan_id = db.Column(db.String(5), db.ForeignKey('kerusakan.kerusakan_id'), nullable=False)
    gejala_id = db.Column(db.String(5), db.ForeignKey('gejala.gejala_id'), nullable=False)
    rule_step = db.Column(db.Integer, nullable=False) # Represents the 'stage' in forward chaining rules

    __table_args__ = (
        db.UniqueConstraint('kerusakan_id', 'gejala_id', name='_kerusakan_gejala_uc'), # Prevent duplicate rules for same K and G
    )

    def __repr__(self):
        return f"<AturanDiagnosis {self.aturan_id} K:{self.kerusakan_id} G:{self.gejala_id}>"

class Solusi(db.Model):
    __tablename__ = 'solusi'
    solusi_id = db.Column(db.Integer, primary_key=True) # Will be auto-incremented
    kerusakan_id = db.Column(db.String(5), db.ForeignKey('kerusakan.kerusakan_id'), nullable=False, unique=True) # One solution per Kerusakan
    penyebab = db.Column(db.Text)
    solusi = db.Column(db.Text)

    def __repr__(self):
        return f"<Solusi {self.kerusakan_id}>"

# Function to populate initial data
def populate_db():
    print("Populating database with initial data...")

    # Create initial users if they don't exist
    if not User.query.filter_by(username='user1').first():
        user = User(username='user1', role='user')
        user.set_password('password')
        db.session.add(user)
    if not User.query.filter_by(username='montir1').first():
        montir = User(username='montir1', role='montir')
        montir.set_password('password')
        db.session.add(montir)

    # Kerusakan data (Start with ID K1, K2 etc. to match data)
    kerusakan_initial_data = [
        {'id': 'K1', 'name': 'Kerusakan Mesin'},
        {'id': 'K2', 'name': 'Kerusakan Kelistrikan'},
        {'id': 'K3', 'name': 'Kerusakan Pengapian'},
        {'id': 'K4', 'name': 'Kerusakan Penggerak Roda'}
    ]
    for data in kerusakan_initial_data:
        if not Kerusakan.query.get(data['id']):
            db.session.add(Kerusakan(kerusakan_id=data['id'], nama_kerusakan=data['name']))

    # Gejala data (Start with ID P1, P2 etc. to match data)
    gejala_initial_data = [
        {'id': 'P1', 'desc': 'Suara mesin kasar'},
        {'id': 'P2', 'desc': 'Mesin susah nyala'},
        {'id': 'P3', 'desc': 'Terdengar kasar pada bagian mesin'},
        {'id': 'P4', 'desc': 'Pada saat di gas suara mesin kasar dan menimbulkan getaran'},
        {'id': 'P5', 'desc': 'Terdapat kebocoran oli pada bagian mesin'},
        # P6 missing based on original document's P1-P5 then P7
        {'id': 'P7', 'desc': 'Aki cepat habis atau drop'},
        {'id': 'P8', 'desc': 'Kabel lampu cepat putus'},
        {'id': 'P9', 'desc': 'Kabel stater mati'},
        {'id': 'P10', 'desc': 'Motor mati total'},
        # P11 missing based on original document's P8-P10 then P12
        {'id': 'P12', 'desc': 'Motor tidak bisa di starter'},
        {'id': 'P13', 'desc': 'Busi masih memercikan api'},
        {'id': 'P14', 'desc': 'Koil terputus atau lepas dari sepul pengapian'},
        # P15 missing
        {'id': 'P16', 'desc': 'CDI konslet'},
        {'id': 'P17', 'desc': 'Sepul mengalami kerusakan'},
        {'id': 'P18', 'desc': 'Terdengar suara berisik pada bagian kiri bawah mesin'},
        {'id': 'P19', 'desc': 'Terdengar suara kasar pada saat motor jalan'},
        {'id': 'P20', 'desc': 'Roda Tidak stabil'},
        {'id': 'P21', 'desc': 'Ban kurang angin'}
        # P22 missing
    ]
    for data in gejala_initial_data:
        if not Gejala.query.get(data['id']):
            db.session.add(Gejala(gejala_id=data['id'], deskripsi_gejala=data['desc']))

    db.session.flush() # Commit changes to get primary keys for relationships

    # AturanDiagnosis data
    aturan_initial_data = [
        # K1 rules (mesin)
        {'kerusakan_id': 'K1', 'gejala_id': 'P1', 'step': 1},
        {'kerusakan_id': 'K1', 'gejala_id': 'P2', 'step': 1},
        {'kerusakan_id': 'K1', 'gejala_id': 'P3', 'step': 1},
        {'kerusakan_id': 'K1', 'gejala_id': 'P4', 'step': 1},
        {'kerusakan_id': 'K1', 'gejala_id': 'P5', 'step': 1},
        # K2 rules (kelistrikan)
        {'kerusakan_id': 'K2', 'gejala_id': 'P7', 'step': 2},
        {'kerusakan_id': 'K2', 'gejala_id': 'P8', 'step': 2},
        {'kerusakan_id': 'K2', 'gejala_id': 'P9', 'step': 2},
        {'kerusakan_id': 'K2', 'gejala_id': 'P10', 'step': 2},
        # K3 rules (pengapian)
        {'kerusakan_id': 'K3', 'gejala_id': 'P12', 'step': 3},
        {'kerusakan_id': 'K3', 'gejala_id': 'P13', 'step': 3},
        {'kerusakan_id': 'K3', 'gejala_id': 'P14', 'step': 3},
        {'kerusakan_id': 'K3', 'gejala_id': 'P16', 'step': 3},
        {'kerusakan_id': 'K3', 'gejala_id': 'P17', 'step': 3},
        # K4 rules (penggerak roda)
        {'kerusakan_id': 'K4', 'gejala_id': 'P18', 'step': 4},
        {'kerusakan_id': 'K4', 'gejala_id': 'P19', 'step': 4},
        {'kerusakan_id': 'K4', 'gejala_id': 'P20', 'step': 4},
        {'kerusakan_id': 'K4', 'gejala_id': 'P21', 'step': 4}
    ]
    for data in aturan_initial_data:
        # Check if rule already exists to prevent duplicates on re-run
        # We use try-except for IntegrityError in case of unique constraint violation (kerusakan_id, gejala_id)
        try:
            if not AturanDiagnosis.query.filter_by(kerusakan_id=data['kerusakan_id'], gejala_id=data['gejala_id']).first():
                db.session.add(AturanDiagnosis(
                    kerusakan_id=data['kerusakan_id'],
                    gejala_id=data['gejala_id'],
                    rule_step=data['step']
                ))
                db.session.flush() # Flush to get ID if needed later in same session
        except Exception as e:
            print(f"Skipping rule {data['kerusakan_id']}-{data['gejala_id']} due to error: {e}")


    # Solusi data (Ensure unique=True on kerusakan_id in Solusi model)
    solusi_initial_data = [
        {'kerusakan_id': 'K1', 'penyebab': 'Karburator yang kotor, Busi yang sudah tidak stabil', 'solusi': 'Service karburator, Cek busi, bila perlu ganti sama yang baru'},
        {'kerusakan_id': 'K2', 'penyebab': 'Masalah pada sistem kelistrikan umum (e.g., baterai, kabel, komponen listrik)', 'solusi': 'Periksa baterai dan sistem pengisian; Periksa dan ganti kabel yang rusak; Uji dan ganti komponen kelistrikan yang bermasalah.'},
        {'kerusakan_id': 'K3', 'penyebab': 'Masalah pada sistem pengapian (e.g., starter, busi, koil, CDI, sepul)', 'solusi': 'Periksa motor starter; Periksa dan ganti busi jika diperlukan; Uji dan ganti koil pengapian; Diagnosis dan ganti CDI yang rusak; Periksa dan perbaiki/ganti sepul (stator).'},
        {'kerusakan_id': 'K4', 'penyebab': 'Masalah pada sistem penggerak roda (e.g., komponen aus, ketidakstabilan, tekanan ban)', 'solusi': 'Periksa komponen sistem penggerak untuk keausan atau kelonggaran; Periksa keseimbangan dan keselarasan roda; Isi ban dengan tekanan yang benar; Perbaiki atau ganti ban/roda yang rusak.'}
    ]
    for data in solusi_initial_data:
        try:
            if not Solusi.query.filter_by(kerusakan_id=data['kerusakan_id']).first():
                db.session.add(Solusi(
                    kerusakan_id=data['kerusakan_id'],
                    penyebab=data['penyebab'],
                    solusi=data['solusi']
                ))
                db.session.flush() # Flush to get ID if needed later in same session
        except Exception as e:
            print(f"Skipping solution for {data['kerusakan_id']} due to error: {e}")

    db.session.commit()
    print("Database population complete.")