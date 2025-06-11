from flask import render_template, request, redirect, url_for, flash, abort
from models import db, Kerusakan, Gejala, AturanDiagnosis, Solusi, User
from flask import Blueprint
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError # For handling unique constraint errors

bp = Blueprint('main', __name__)

# Decorator for role-based access control
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Anda harus login untuk mengakses halaman ini.', 'warning')
                return redirect(url_for('main.login'))
            if current_user.role != role:
                flash('Anda tidak memiliki izin untuk mengakses halaman ini.', 'danger')
                # For unauthorized access, better to use abort(403) or redirect to a custom error page
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Authentication Routes ---
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # For security, 'montir' role should ideally be assigned by an admin,
        # not freely selectable during registration in a production app.
        role = request.form.get('role', 'user')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Nama pengguna sudah ada. Silakan pilih nama lain.', 'danger')
        else:
            new_user = User(username=username, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registrasi berhasil! Anda sekarang dapat login.', 'success')
            return redirect(url_for('main.login'))
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Selamat datang, {user.username}!', 'success')
            if user.role == 'montir':
                return redirect(url_for('main.montir_dashboard'))
            return redirect(url_for('main.diagnose'))
        else:
            flash('Username atau password salah.', 'danger')
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('main.index'))

# --- Main Application Routes ---
@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/diagnose', methods=['GET', 'POST'])
@login_required
def diagnose():
    if request.method == 'POST':
        selected_gejala_ids = request.form.getlist('gejala')

        if not selected_gejala_ids:
            flash('Pilih setidaknya satu gejala untuk diagnosa.', 'warning')
            return redirect(url_for('main.diagnose'))

        # Expert System Logic: Forward Chaining
        # Eagerly load rules and their associated gejala for efficient checking
        all_possible_diagnoses = Kerusakan.query.options(joinedload(Kerusakan.rules).joinedload(AturanDiagnosis.gejala)).all()

        found_diagnosis = None
        for kerusakan in all_possible_diagnoses:
            required_gejala_for_kerusakan = [
                aturan.gejala_id for aturan in kerusakan.rules
            ]

            # If there are no rules defined for this 'kerusakan', it cannot be diagnosed by rules
            if not required_gejala_for_kerusakan:
                continue # Skip this kerusakan if it has no rules

            all_symptoms_present = True
            for required_gejala_id in required_gejala_for_kerusakan:
                if required_gejala_id not in selected_gejala_ids:
                    all_symptoms_present = False
                    break # If even one required symptom is missing, this damage cannot be concluded

            if all_symptoms_present:
                found_diagnosis = kerusakan
                break # Found a diagnosis, stop checking further

        if found_diagnosis:
            return redirect(url_for('main.result', kerusakan_id=found_diagnosis.kerusakan_id))
        else:
            flash('Tidak ada diagnosa pasti yang dapat dibuat berdasarkan gejala yang dipilih.', 'info')
            return redirect(url_for('main.diagnose'))

    all_gejala = Gejala.query.all()
    return render_template('diagnose.html', gejala=all_gejala)

@bp.route('/result/<kerusakan_id>')
@login_required
def result(kerusakan_id):
    kerusakan = Kerusakan.query.get_or_404(kerusakan_id)
    solusi = Solusi.query.filter_by(kerusakan_id=kerusakan_id).first() # Assuming one solution per Kerusakan
    return render_template('result.html', kerusakan=kerusakan, solusi=solusi)


# --- Montir-specific Routes ---
@bp.route('/montir_dashboard')
@role_required('montir')
def montir_dashboard():
    all_kerusakan = Kerusakan.query.options(joinedload(Kerusakan.solutions)).all()
    all_gejala = Gejala.query.all()
    # Eagerly load associated Kerusakan and Gejala objects for display
    all_rules = AturanDiagnosis.query.options(joinedload(AturanDiagnosis.kerusakan), joinedload(AturanDiagnosis.gejala)).order_by(AturanDiagnosis.kerusakan_id, AturanDiagnosis.rule_step).all()

    return render_template('montir_dashboard.html',
                           kerusakan=all_kerusakan,
                           gejala=all_gejala,
                           all_rules=all_rules) # Variable name is now 'all_rules'

# --- CRUD for Kerusakan (Damage Types) ---
@bp.route('/montir/add_kerusakan', methods=['GET', 'POST'])
@role_required('montir')
def add_kerusakan():
    if request.method == 'POST':
        kerusakan_id = request.form['kerusakan_id'].strip().upper() # Standardize ID
        nama_kerusakan = request.form['nama_kerusakan'].strip()

        if not kerusakan_id or not nama_kerusakan:
            flash('ID Kerusakan dan Nama Kerusakan tidak boleh kosong.', 'danger')
            return render_template('add_kerusakan.html')

        if Kerusakan.query.get(kerusakan_id):
            flash(f'ID Kerusakan "{kerusakan_id}" sudah ada. Gunakan ID lain.', 'danger')
            return render_template('add_kerusakan.html')

        new_kerusakan = Kerusakan(kerusakan_id=kerusakan_id, nama_kerusakan=nama_kerusakan)
        db.session.add(new_kerusakan)
        try:
            db.session.commit()
            flash(f'Kerusakan "{nama_kerusakan}" ({kerusakan_id}) berhasil ditambahkan!', 'success')
            return redirect(url_for('main.montir_dashboard'))
        except IntegrityError: # In case of unique constraint violation (unlikely if checked above, but good practice)
            db.session.rollback()
            flash('Terjadi kesalahan. ID Kerusakan mungkin sudah ada.', 'danger')
            return render_template('add_kerusakan.html')
    return render_template('add_kerusakan.html')

@bp.route('/montir/edit_kerusakan/<string:kerusakan_id_to_edit>', methods=['GET', 'POST'])
@role_required('montir')
def edit_kerusakan(kerusakan_id_to_edit):
    kerusakan = Kerusakan.query.get_or_404(kerusakan_id_to_edit)
    if request.method == 'POST':
        new_nama_kerusakan = request.form['nama_kerusakan'].strip()
        # New ID is only allowed if it doesn't conflict and is different
        new_kerusakan_id = request.form['kerusakan_id'].strip().upper()

        if not new_nama_kerusakan or not new_kerusakan_id:
            flash('ID Kerusakan dan Nama Kerusakan tidak boleh kosong.', 'danger')
            return render_template('edit_kerusakan.html', kerusakan=kerusakan)

        if new_kerusakan_id != kerusakan.kerusakan_id and Kerusakan.query.get(new_kerusakan_id):
            flash(f'ID Kerusakan "{new_kerusakan_id}" sudah digunakan oleh kerusakan lain.', 'danger')
            return render_template('edit_kerusakan.html', kerusakan=kerusakan)

        # Update attributes
        kerusakan.nama_kerusakan = new_nama_kerusakan
        # If ID changed, this needs special handling due to primary key and relationships.
        # For simplicity, let's assume changing primary key is not allowed directly here
        # or implies complex cascade rules not handled by simple update if relationships exist.
        # If you really need to change PK, it's safer to delete old and create new with CASCADE.
        # For this example, we'll primarily allow editing the name.
        if new_kerusakan_id != kerusakan.kerusakan_id:
            flash("Perubahan ID Kerusakan tidak didukung langsung. Silakan hapus dan buat ulang jika ingin mengubah ID.", 'warning')
            # It's usually better to just change the non-PK fields in an edit form.
            # If PK change is crucial, it's typically a 'delete and recreate' operation.
            return redirect(url_for('main.montir_dashboard')) # Or stay on page

        try:
            db.session.commit()
            flash(f'Kerusakan "{kerusakan.nama_kerusakan}" berhasil diperbarui!', 'success')
            return redirect(url_for('main.montir_dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash('Terjadi kesalahan saat memperbarui kerusakan. Mungkin ID baru sudah ada atau konflik.', 'danger')
            return render_template('edit_kerusakan.html', kerusakan=kerusakan)
    return render_template('edit_kerusakan.html', kerusakan=kerusakan)

@bp.route('/montir/delete_kerusakan/<string:kerusakan_id_to_delete>', methods=['POST'])
@role_required('montir')
def delete_kerusakan(kerusakan_id_to_delete):
    kerusakan = Kerusakan.query.get_or_404(kerusakan_id_to_delete)
    try:
        db.session.delete(kerusakan)
        db.session.commit()
        flash(f'Kerusakan "{kerusakan.nama_kerusakan}" dan semua aturan/solusi terkait berhasil dihapus.', 'success')
    except IntegrityError: # If there's a constraint that cascade='all, delete-orphan' didn't catch
        db.session.rollback()
        flash('Tidak dapat menghapus kerusakan ini karena ada referensi data lain.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Terjadi kesalahan saat menghapus kerusakan: {e}', 'danger')
    return redirect(url_for('main.montir_dashboard'))

# --- CRUD for Gejala (Symptoms) ---
@bp.route('/montir/add_gejala', methods=['GET', 'POST'])
@role_required('montir')
def add_gejala():
    if request.method == 'POST':
        gejala_id = request.form['gejala_id'].strip().upper() # Standardize ID
        deskripsi_gejala = request.form['deskripsi_gejala'].strip()

        if not gejala_id or not deskripsi_gejala:
            flash('ID Gejala dan Deskripsi Gejala tidak boleh kosong.', 'danger')
            return render_template('add_gejala.html')

        if Gejala.query.get(gejala_id):
            flash(f'ID Gejala "{gejala_id}" sudah ada. Gunakan ID lain.', 'danger')
            return render_template('add_gejala.html')

        new_gejala = Gejala(gejala_id=gejala_id, deskripsi_gejala=deskripsi_gejala)
        db.session.add(new_gejala)
        try:
            db.session.commit()
            flash(f'Gejala "{deskripsi_gejala}" ({gejala_id}) berhasil ditambahkan!', 'success')
            return redirect(url_for('main.montir_dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash('Terjadi kesalahan. ID Gejala mungkin sudah ada.', 'danger')
            return render_template('add_gejala.html')
    return render_template('add_gejala.html')

@bp.route('/montir/edit_gejala/<string:gejala_id_to_edit>', methods=['GET', 'POST'])
@role_required('montir')
def edit_gejala(gejala_id_to_edit):
    gejala = Gejala.query.get_or_404(gejala_id_to_edit)
    if request.method == 'POST':
        new_deskripsi_gejala = request.form['deskripsi_gejala'].strip()
        new_gejala_id = request.form['gejala_id'].strip().upper()

        if not new_deskripsi_gejala or not new_gejala_id:
            flash('ID Gejala dan Deskripsi Gejala tidak boleh kosong.', 'danger')
            return render_template('edit_gejala.html', gejala=gejala)

        if new_gejala_id != gejala.gejala_id and Gejala.query.get(new_gejala_id):
            flash(f'ID Gejala "{new_gejala_id}" sudah digunakan oleh gejala lain.', 'danger')
            return render_template('edit_gejala.html', gejala=gejala)

        gejala.deskripsi_gejala = new_deskripsi_gejala
        if new_gejala_id != gejala.gejala_id:
            flash("Perubahan ID Gejala tidak didukung langsung. Silakan hapus dan buat ulang jika ingin mengubah ID.", 'warning')

        try:
            db.session.commit()
            flash(f'Gejala "{gejala.deskripsi_gejala}" berhasil diperbarui!', 'success')
            return redirect(url_for('main.montir_dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash('Terjadi kesalahan saat memperbarui gejala. Mungkin ID baru sudah ada atau konflik.', 'danger')
            return render_template('edit_gejala.html', gejala=gejala)
    return render_template('edit_gejala.html', gejala=gejala)

@bp.route('/montir/delete_gejala/<string:gejala_id_to_delete>', methods=['POST'])
@role_required('montir')
def delete_gejala(gejala_id_to_delete):
    gejala = Gejala.query.get_or_404(gejala_id_to_delete)
    try:
        db.session.delete(gejala)
        db.session.commit()
        flash(f'Gejala "{gejala.deskripsi_gejala}" dan semua aturan terkait berhasil dihapus.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Tidak dapat menghapus gejala ini karena ada referensi data lain.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Terjadi kesalahan saat menghapus gejala: {e}', 'danger')
    return redirect(url_for('main.montir_dashboard'))


# --- CRUD for AturanDiagnosis (Rules) ---
# Add rule route is already there: @bp.route('/montir/add_rule', methods=['GET', 'POST'])
# from previous code, it's already in routes.py
# @bp.route('/montir/add_rule', methods=['GET', 'POST'])
# @role_required('montir')
# def add_rule():
#    ... (existing add_rule function) ...

@bp.route('/montir/delete_rule/<int:aturan_id_to_delete>', methods=['POST'])
@role_required('montir')
def delete_rule(aturan_id_to_delete):
    rule = AturanDiagnosis.query.get_or_404(aturan_id_to_delete)
    try:
        db.session.delete(rule)
        db.session.commit()
        flash(f'Aturan (ID: {rule.aturan_id}) berhasil dihapus.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Terjadi kesalahan saat menghapus aturan: {e}', 'danger')
    return redirect(url_for('main.montir_dashboard'))

# --- CRUD for AturanDiagnosis (Rules) ---
@bp.route('/montir/add_rule', methods=['GET', 'POST'])
@role_required('montir')
def add_rule():
    if request.method == 'POST':
        kerusakan_id = request.form['kerusakan_id'].strip()
        gejala_id = request.form['gejala_id'].strip()
        rule_step = request.form['rule_step'].strip()

        if not kerusakan_id or not gejala_id or not rule_step:
            flash('ID Kerusakan, ID Gejala, dan Tahap Aturan tidak boleh kosong.', 'danger')
            # Fetch options again for re-rendering the form
            kerusakan_options = Kerusakan.query.all()
            gejala_options = Gejala.query.all()
            return render_template('add_rule.html', kerusakan_options=kerusakan_options, gejala_options=gejala_options)

        # Basic validation for existence of Kerusakan and Gejala
        if not Kerusakan.query.get(kerusakan_id):
            flash('ID Kerusakan tidak valid.', 'danger')
            kerusakan_options = Kerusakan.query.all()
            gejala_options = Gejala.query.all()
            return render_template('add_rule.html', kerusakan_options=kerusakan_options, gejala_options=gejala_options)

        if not Gejala.query.get(gejala_id):
            flash('ID Gejala tidak valid.', 'danger')
            kerusakan_options = Kerusakan.query.all()
            gejala_options = Gejala.query.all()
            return render_template('add_rule.html', kerusakan_options=kerusakan_options, gejala_options=gejala_options)

        # Check for duplicate rule
        if AturanDiagnosis.query.filter_by(kerusakan_id=kerusakan_id, gejala_id=gejala_id).first():
            flash('Aturan ini sudah ada untuk kombinasi Kerusakan dan Gejala ini.', 'warning')
            kerusakan_options = Kerusakan.query.all()
            gejala_options = Gejala.query.all()
            return render_template('add_rule.html', kerusakan_options=kerusakan_options, gejala_options=gejala_options)

        new_rule = AturanDiagnosis(kerusakan_id=kerusakan_id, gejala_id=gejala_id, rule_step=int(rule_step))
        db.session.add(new_rule)
        try:
            db.session.commit()
            flash('Aturan berhasil ditambahkan!', 'success')
            return redirect(url_for('main.montir_dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash('Terjadi kesalahan saat menambahkan aturan. Mungkin ID Kerusakan atau Gejala tidak cocok.', 'danger')
            kerusakan_options = Kerusakan.query.all()
            gejala_options = Gejala.query.all()
            return render_template('add_rule.html', kerusakan_options=kerusakan_options, gejala_options=gejala_options)
        except ValueError:
            db.session.rollback()
            flash('Tahap Aturan harus berupa angka yang valid.', 'danger')
            kerusakan_options = Kerusakan.query.all()
            gejala_options = Gejala.query.all()
            return render_template('add_rule.html', kerusakan_options=kerusakan_options, gejala_options=gejala_options)

    kerusakan_options = Kerusakan.query.all()
    gejala_options = Gejala.query.all()
    return render_template('add_rule.html', kerusakan_options=kerusakan_options, gejala_options=gejala_options)

@bp.route('/montir/edit_solusi/<string:kerusakan_id>', methods=['GET', 'POST'])
@role_required('montir')
def edit_solusi(kerusakan_id):
    kerusakan = Kerusakan.query.get_or_404(kerusakan_id)
    solusi = Solusi.query.filter_by(kerusakan_id=kerusakan_id).first()

    if request.method == 'POST':
        penyebab = request.form['penyebab'].strip()
        solusi_text = request.form['solusi'].strip()

        if not solusi:
            solusi = Solusi(kerusakan_id=kerusakan_id, penyebab=penyebab, solusi=solusi_text)
            db.session.add(solusi)
        else:
            solusi.penyebab = penyebab
            solusi.solusi = solusi_text
        try:
            db.session.commit()
            flash(f'Solusi untuk {kerusakan.nama_kerusakan} berhasil diperbarui!', 'success')
            return redirect(url_for('main.montir_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Terjadi kesalahan saat menyimpan solusi: {e}', 'danger')
            return render_template('edit_solusi.html', kerusakan=kerusakan, solusi=solusi)

    return render_template('edit_solusi.html', kerusakan=kerusakan, solusi=solusi)
