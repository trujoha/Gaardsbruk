# ============================================================================
# KSL Digital - Digitale sjekklister for kvalitetsstyring i landbruket
# ============================================================================

from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import json
import os
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gaardsbruk-dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///gaardsbruk.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# ============================================================================
# DATABASE
# ============================================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brukernavn = db.Column(db.String(80), unique=True, nullable=False)
    passord_hash = db.Column(db.String(256), nullable=False)
    navn = db.Column(db.String(120), nullable=False)
    er_admin = db.Column(db.Boolean, default=False)
    opprettet = db.Column(db.DateTime, default=datetime.now)

    def sett_passord(self, passord):
        self.passord_hash = generate_password_hash(passord)

    def sjekk_passord(self, passord):
        return check_password_hash(self.passord_hash, passord)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Gaard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    navn = db.Column(db.String(200), nullable=False)
    org_nr = db.Column(db.String(20), default='')
    adresse = db.Column(db.String(300), default='')
    produksjoner = db.Column(db.Text, default='[]')  # JSON liste
    opprettet = db.Column(db.DateTime, default=datetime.now)


class Revisjon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gaard_id = db.Column(db.Integer, db.ForeignKey('gaard.id'), nullable=False)
    sjekkliste_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='paagaar')  # paagaar, fullfort
    antall_ok = db.Column(db.Integer, default=0)
    antall_avvik = db.Column(db.Integer, default=0)
    antall_ir = db.Column(db.Integer, default=0)
    signert_av = db.Column(db.String(200), default='')
    signert_dato = db.Column(db.DateTime, nullable=True)
    opprettet = db.Column(db.DateTime, default=datetime.now)


class SjekklisteSvar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    revisjon_id = db.Column(db.Integer, db.ForeignKey('revisjon.id'), nullable=False)
    punkt_id = db.Column(db.String(20), nullable=False)
    svar = db.Column(db.String(20), default='')  # ok, avvik, ir (ikke relevant)
    kommentar = db.Column(db.Text, default='')
    bilde_sti = db.Column(db.String(500), default='')
    besvart = db.Column(db.DateTime, default=datetime.now)


class GjodselJournal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gaard_id = db.Column(db.Integer, default=1)
    dato = db.Column(db.Date, nullable=False)
    skifte = db.Column(db.String(100))
    areal_daa = db.Column(db.Float, default=0)
    gjodseltype = db.Column(db.String(100))
    mengde = db.Column(db.Float, default=0)
    enhet = db.Column(db.String(20))
    nitrogen_kg = db.Column(db.Float, default=0)
    fosfor_kg = db.Column(db.Float, default=0)
    kalium_kg = db.Column(db.Float, default=0)
    metode = db.Column(db.String(100))
    vaer = db.Column(db.String(50))
    notat = db.Column(db.Text, default='')
    opprettet = db.Column(db.DateTime, default=datetime.now)


class SproyteJournal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gaard_id = db.Column(db.Integer, default=1)
    dato = db.Column(db.Date, nullable=False)
    skifte = db.Column(db.String(100))
    areal_daa = db.Column(db.Float, default=0)
    preparat = db.Column(db.String(200))
    dose_per_daa = db.Column(db.Float, default=0)
    total_mengde = db.Column(db.Float, default=0)
    enhet = db.Column(db.String(20))
    vekst = db.Column(db.String(100))
    skadegjorer = db.Column(db.String(200))
    vaer = db.Column(db.String(50))
    temperatur = db.Column(db.Float, nullable=True)
    vind = db.Column(db.String(50))
    behandlingsfrist = db.Column(db.Integer, default=0)
    notat = db.Column(db.Text, default='')
    opprettet = db.Column(db.DateTime, default=datetime.now)


class DyreholdLogg(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gaard_id = db.Column(db.Integer, default=1)
    dato = db.Column(db.Date, nullable=False)
    dyr_id = db.Column(db.String(50))
    dyreart = db.Column(db.String(50))
    hendelse = db.Column(db.String(50))
    beskrivelse = db.Column(db.Text, default='')
    medisin = db.Column(db.String(200), default='')
    tilbakeholdelse_dager = db.Column(db.Integer, default=0)
    veteriner = db.Column(db.String(100), default='')
    opprettet = db.Column(db.DateTime, default=datetime.now)


class VedlikeholdsLogg(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gaard_id = db.Column(db.Integer, default=1)
    dato = db.Column(db.Date, nullable=False)
    maskin = db.Column(db.String(200))
    type_vedlikehold = db.Column(db.String(50))
    beskrivelse = db.Column(db.Text, default='')
    kostnad = db.Column(db.Float, default=0)
    utfort_av = db.Column(db.String(100), default='')
    neste_service = db.Column(db.Date, nullable=True)
    opprettet = db.Column(db.DateTime, default=datetime.now)


class AvfallsLogg(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gaard_id = db.Column(db.Integer, default=1)
    dato = db.Column(db.Date, nullable=False)
    avfallstype = db.Column(db.String(100))
    mengde = db.Column(db.Float, default=0)
    enhet = db.Column(db.String(20))
    mottaker = db.Column(db.String(200), default='')
    notat = db.Column(db.Text, default='')
    opprettet = db.Column(db.DateTime, default=datetime.now)


class Oppsynslogg(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gaard_id = db.Column(db.Integer, default=1)
    dato = db.Column(db.Date, nullable=False)
    sted = db.Column(db.String(200))
    km_tur_retur = db.Column(db.Float, default=0)
    timer = db.Column(db.Float, default=0)
    antall_dyr_sett = db.Column(db.Integer, default=0)
    observasjoner = db.Column(db.Text, default='')
    opprettet = db.Column(db.DateTime, default=datetime.now)


class Kjorebok(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gaard_id = db.Column(db.Integer, default=1)
    dato = db.Column(db.Date, nullable=False)
    formaal = db.Column(db.String(200))
    fra_sted = db.Column(db.String(200), default='')
    til_sted = db.Column(db.String(200), default='')
    km_start = db.Column(db.Float, default=0)
    km_slutt = db.Column(db.Float, default=0)
    distanse = db.Column(db.Float, default=0)
    type_kjoering = db.Column(db.String(20), default='gaard')
    notat = db.Column(db.Text, default='')
    opprettet = db.Column(db.DateTime, default=datetime.now)


# ============================================================================
# SJEKKLISTE-DATA (fra KSL standarder)
# ============================================================================

SJEKKLISTER = {
    "generelt": {
        "navn": "Generelle krav",
        "ikon": "🏠",
        "farge": "#1a3c2a",
        "punkter": [
            {"id": "G01", "kategori": "HMS", "tekst": "Er det gjennomfoert HMS-kartlegging det siste aaret?", "krav": "Arbeidsmiljoeloven"},
            {"id": "G02", "kategori": "HMS", "tekst": "Er verneombud/HMS-ansvarlig utpekt?", "krav": "AML kap. 6"},
            {"id": "G03", "kategori": "HMS", "tekst": "Finnes oppdatert stoffkartotek for kjemikalier?", "krav": "Forskrift om utfoerelse av arbeid"},
            {"id": "G04", "kategori": "HMS", "tekst": "Er noedvendig verneutstyr tilgjengelig og i god stand?", "krav": "AML"},
            {"id": "G05", "kategori": "Brannvern", "tekst": "Er brannslokker kontrollert siste 12 mnd?", "krav": "Forskrift om brannforebygging"},
            {"id": "G06", "kategori": "Brannvern", "tekst": "Er roemningsveier merket og frie?", "krav": "Forskrift om brannforebygging"},
            {"id": "G07", "kategori": "Brannvern", "tekst": "Er det gjennomfoert el-kontroll siste 5 aar?", "krav": "NEK 400"},
            {"id": "G08", "kategori": "Avfall", "tekst": "Er farlig avfall sortert og merket?", "krav": "Avfallsforskriften"},
            {"id": "G09", "kategori": "Avfall", "tekst": "Er det avtale med godkjent avfallsmottaker?", "krav": "Forurensningsloven"},
            {"id": "G10", "kategori": "Dokumentasjon", "tekst": "Er driftsplan oppdatert?", "krav": "KSL-standard"},
            {"id": "G11", "kategori": "Dokumentasjon", "tekst": "Er forsikringer oppdatert?", "krav": "KSL-standard"},
            {"id": "G12", "kategori": "Dokumentasjon", "tekst": "Er journal foert for plantevernmidler?", "krav": "Plantevernmiddelforskriften"},
        ]
    },
    "melk": {
        "navn": "Melkeproduksjon",
        "ikon": "🐄",
        "farge": "#1565c0",
        "punkter": [
            {"id": "M01", "kategori": "Dyrevelferd", "tekst": "Har alle dyr tilgang paa rent drikkevann?", "krav": "Dyrevelferdsloven"},
            {"id": "M02", "kategori": "Dyrevelferd", "tekst": "Er liggearealet tilstrekkelig og rent?", "krav": "Forskrift om hold av storfe"},
            {"id": "M03", "kategori": "Dyrevelferd", "tekst": "Fungerer ventilasjon tilfredsstillende?", "krav": "Forskrift om hold av storfe"},
            {"id": "M04", "kategori": "Dyrevelferd", "tekst": "Er det daglig tilsyn med alle dyr?", "krav": "Dyrevelferdsloven §24"},
            {"id": "M05", "kategori": "Dyrevelferd", "tekst": "Er sykebinge tilgjengelig?", "krav": "Forskrift om hold av storfe"},
            {"id": "M06", "kategori": "Melkekvalitet", "tekst": "Er melkeanlegget rengjort etter hver melking?", "krav": "Hygieneregler"},
            {"id": "M07", "kategori": "Melkekvalitet", "tekst": "Er kjoeletank kontrollert og fungerer?", "krav": "KSL melk"},
            {"id": "M08", "kategori": "Melkekvalitet", "tekst": "Er melkeprover tatt iht plan?", "krav": "TINE avtale"},
            {"id": "M09", "kategori": "Foring", "tekst": "Er foret lagret torrt og beskyttet?", "krav": "KSL-standard"},
            {"id": "M10", "kategori": "Foring", "tekst": "Er foeringsplan oppdatert?", "krav": "KSL melk"},
            {"id": "M11", "kategori": "Helse", "tekst": "Er helsekort oppdatert for alle dyr?", "krav": "Dyrehelsepersonelloven"},
            {"id": "M12", "kategori": "Helse", "tekst": "Er medisiner lagret forskriftsmessig?", "krav": "Legemiddelloven"},
        ]
    },
    "storfekjott": {
        "navn": "Storfekjoettproduksjon",
        "ikon": "🥩",
        "farge": "#c62828",
        "punkter": [
            {"id": "S01", "kategori": "Dyrevelferd", "tekst": "Er alle dyr oeremerket og registrert i Husdyrregisteret?", "krav": "Forskrift om merking av storfe"},
            {"id": "S02", "kategori": "Dyrevelferd", "tekst": "Er det tilstrekkelig plass per dyr iht forskrift?", "krav": "Forskrift om hold av storfe"},
            {"id": "S03", "kategori": "Dyrevelferd", "tekst": "Har dyr paa beite tilgang paa ly/skygge?", "krav": "Dyrevelferdsloven"},
            {"id": "S04", "kategori": "Dyrevelferd", "tekst": "Er klauvpleie gjennomfoert?", "krav": "KSL storfe"},
            {"id": "S05", "kategori": "Foring", "tekst": "Er grovfortilgang tilstrekkelig?", "krav": "Forskrift om hold av storfe"},
            {"id": "S06", "kategori": "Helse", "tekst": "Er vaksinasjonsplan fulgt?", "krav": "Veterinaeravtale"},
            {"id": "S07", "kategori": "Helse", "tekst": "Er smittevern ivaretatt ved innsett av nye dyr?", "krav": "Dyrehelsepersonelloven"},
            {"id": "S08", "kategori": "Transport", "tekst": "Er transportbil godkjent for dyretransport?", "krav": "Transportforskriften"},
        ]
    },
    "sau": {
        "navn": "Sau og geit",
        "ikon": "🐑",
        "farge": "#7b1fa2",
        "punkter": [
            {"id": "SG01", "kategori": "Dyrevelferd", "tekst": "Er alle dyr merket iht forskrift?", "krav": "Forskrift om merking"},
            {"id": "SG02", "kategori": "Dyrevelferd", "tekst": "Er klipping gjennomfoert foer sommerbeite?", "krav": "KSL sau"},
            {"id": "SG03", "kategori": "Dyrevelferd", "tekst": "Er det gjennomfoert parasittbehandling?", "krav": "Veterinaeravtale"},
            {"id": "SG04", "kategori": "Beite", "tekst": "Er gjerder kontrollert foer beiteslipp?", "krav": "Dyrevelferdsloven"},
            {"id": "SG05", "kategori": "Beite", "tekst": "Er tilsynsplan for utmarksbeite laget?", "krav": "Dyrevelferdsloven"},
            {"id": "SG06", "kategori": "Helse", "tekst": "Er flokkhelsebesoeek gjennomfoert?", "krav": "KSL sau"},
            {"id": "SG07", "kategori": "Lamming", "tekst": "Er lammingsopplegg og beredskap planlagt?", "krav": "KSL sau"},
            {"id": "SG08", "kategori": "Dokumentasjon", "tekst": "Er sauekontrollen oppdatert?", "krav": "Animalia"},
        ]
    },
    "plante": {
        "navn": "Planteproduksjon",
        "ikon": "🌾",
        "farge": "#2e7d32",
        "punkter": [
            {"id": "P01", "kategori": "Plantevernmidler", "tekst": "Har sproeytefoerer gyldig autorisasjonsbevis?", "krav": "Plantevernmiddelforskriften"},
            {"id": "P02", "kategori": "Plantevernmidler", "tekst": "Er sproeytejournal foert for alle behandlinger?", "krav": "Plantevernmiddelforskriften"},
            {"id": "P03", "kategori": "Plantevernmidler", "tekst": "Er aakerspoeyter funksjonstestet siste 5 aar?", "krav": "Plantevernmiddelforskriften"},
            {"id": "P04", "kategori": "Plantevernmidler", "tekst": "Er plantevernmidler lagret i laast skap?", "krav": "Plantevernmiddelforskriften"},
            {"id": "P05", "kategori": "Gjodsel", "tekst": "Er gjodslingsplan laget basert paa jordprover?", "krav": "Forskrift om gjodslingsplanlegging"},
            {"id": "P06", "kategori": "Gjodsel", "tekst": "Er jordprover tatt siste 8 aar?", "krav": "Forskrift om gjodslingsplanlegging"},
            {"id": "P07", "kategori": "Gjodsel", "tekst": "Er husdyrgjodsel lagret uten avrenning?", "krav": "Forurensningsforskriften"},
            {"id": "P08", "kategori": "Gjodsel", "tekst": "Er spredeareal tilstrekkelig for gjoedselmengde?", "krav": "Forskrift om organisk gjodsel"},
            {"id": "P09", "kategori": "Jord", "tekst": "Er det iverksatt tiltak mot erosjon?", "krav": "KSL plante"},
            {"id": "P10", "kategori": "Dokumentasjon", "tekst": "Er skifteplan/kartoversikt oppdatert?", "krav": "KSL plante"},
        ]
    },
    "svin": {
        "navn": "Svineproduksjon",
        "ikon": "🐷",
        "farge": "#e65100",
        "punkter": [
            {"id": "SV01", "kategori": "Dyrevelferd", "tekst": "Er det tilstrekkelig rotemateriale/stroe?", "krav": "Forskrift om hold av svin"},
            {"id": "SV02", "kategori": "Dyrevelferd", "tekst": "Er bingeareal iht forskrift?", "krav": "Forskrift om hold av svin"},
            {"id": "SV03", "kategori": "Dyrevelferd", "tekst": "Er halebiting registrert og tiltak iverksatt?", "krav": "Dyrevelferdsloven"},
            {"id": "SV04", "kategori": "Smittevern", "tekst": "Er smittesluse/skifterom i bruk?", "krav": "KSL svin"},
            {"id": "SV05", "kategori": "Smittevern", "tekst": "Er besoeksprotokoll foert?", "krav": "KSL svin"},
            {"id": "SV06", "kategori": "Helse", "tekst": "Er helsegrisen oppdatert?", "krav": "Animalia"},
            {"id": "SV07", "kategori": "Foring", "tekst": "Er vannforsyning kontrollert?", "krav": "Forskrift om hold av svin"},
            {"id": "SV08", "kategori": "Miljoe", "tekst": "Er ammoniakknivaa akseptabelt?", "krav": "KSL svin"},
        ]
    },
}


# Opprett tabeller
with app.app_context():
    db.create_all()
    if User.query.count() == 0:
        admin = User(brukernavn='admin', navn='Administrator', er_admin=True)
        admin.sett_passord('Gaardsbruk2026!')
        db.session.add(admin)
        db.session.commit()
    if Gaard.query.count() == 0:
        demo = Gaard(navn='Demo Gaard', org_nr='999888777', adresse='Gardsvegen 1, 2390 Moelv',
                     produksjoner=json.dumps(['melk', 'plante']))
        db.session.add(demo)
        db.session.commit()


# ============================================================================
# SIDER
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        brukernavn = request.form.get('brukernavn', '')
        passord = request.form.get('passord', '')
        user = User.query.filter_by(brukernavn=brukernavn).first()
        if user and user.sjekk_passord(passord):
            login_user(user)
            return redirect(url_for('index'))
        return render_template('login.html', feil='Feil brukernavn eller passord')
    return render_template('login.html')


@app.route('/logg-ut')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/sjekkliste/<sjekkliste_type>')
@login_required
def sjekkliste_side(sjekkliste_type):
    return render_template('sjekkliste.html', sjekkliste_type=sjekkliste_type)


@app.route('/historikk')
@login_required
def historikk_side():
    return render_template('historikk.html')


@app.route('/pitch')
def pitch_side():
    return render_template('pitch.html')


@app.route('/admin')
@login_required
def admin_side():
    if not current_user.er_admin:
        return redirect(url_for('index'))
    return render_template('admin.html')


@app.route('/api/admin/brukere', methods=['GET'])
@login_required
def hent_brukere():
    if not current_user.er_admin:
        return jsonify({"error": "Ingen tilgang"}), 403
    brukere = User.query.all()
    return jsonify({"success": True, "brukere": [
        {"id": u.id, "brukernavn": u.brukernavn, "navn": u.navn, "er_admin": u.er_admin}
        for u in brukere
    ]})


@app.route('/api/admin/bruker', methods=['POST'])
@login_required
def opprett_bruker():
    if not current_user.er_admin:
        return jsonify({"error": "Ingen tilgang"}), 403
    data = request.get_json()
    if User.query.filter_by(brukernavn=data['brukernavn']).first():
        return jsonify({"success": False, "error": "Brukernavn finnes allerede"}), 400
    u = User(brukernavn=data['brukernavn'], navn=data.get('navn', ''), er_admin=data.get('er_admin', False))
    u.sett_passord(data['passord'])
    db.session.add(u)
    db.session.commit()
    return jsonify({"success": True, "message": f"Bruker '{data['brukernavn']}' opprettet"})


@app.route('/api/admin/bruker/<int:uid>', methods=['DELETE'])
@login_required
def slett_bruker(uid):
    if not current_user.er_admin:
        return jsonify({"error": "Ingen tilgang"}), 403
    u = User.query.get(uid)
    if not u:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404
    if u.brukernavn == 'admin':
        return jsonify({"success": False, "error": "Kan ikke slette admin"}), 400
    db.session.delete(u)
    db.session.commit()
    return jsonify({"success": True})


# ============================================================================
# JOURNAL-SIDER
# ============================================================================

@app.route('/gjodseljournal')
@login_required
def gjodseljournal_side():
    return render_template('gjodseljournal.html')


@app.route('/sproytejournal')
@login_required
def sproytejournal_side():
    return render_template('sproytejournal.html')


@app.route('/dyrehold')
@login_required
def dyrehold_side():
    return render_template('dyrehold.html')


@app.route('/vedlikehold')
@login_required
def vedlikehold_side():
    return render_template('vedlikehold.html')


@app.route('/avfall')
@login_required
def avfall_side():
    return render_template('avfall.html')


@app.route('/oppsynslogg')
@login_required
def oppsynslogg_side():
    return render_template('oppsynslogg.html')


@app.route('/kjorebok')
@login_required
def kjorebok_side():
    return render_template('kjorebok.html')


# ============================================================================
# JOURNAL API-er
# ============================================================================

# --- Gjodseljournal ---
@app.route('/api/gjodseljournal', methods=['GET'])
@login_required
def hent_gjodseljournal():
    q = GjodselJournal.query
    fra = request.args.get('fra')
    til = request.args.get('til')
    if fra:
        q = q.filter(GjodselJournal.dato >= date.fromisoformat(fra))
    if til:
        q = q.filter(GjodselJournal.dato <= date.fromisoformat(til))
    oppf = q.order_by(GjodselJournal.dato.desc()).all()
    return jsonify({"success": True, "data": [{
        "id": o.id, "dato": o.dato.isoformat(), "skifte": o.skifte, "areal_daa": o.areal_daa,
        "gjodseltype": o.gjodseltype, "mengde": o.mengde, "enhet": o.enhet,
        "nitrogen_kg": o.nitrogen_kg, "fosfor_kg": o.fosfor_kg, "kalium_kg": o.kalium_kg,
        "metode": o.metode, "vaer": o.vaer, "notat": o.notat
    } for o in oppf]})


@app.route('/api/gjodseljournal', methods=['POST'])
@login_required
def ny_gjodseljournal():
    d = request.get_json()
    o = GjodselJournal(
        dato=date.fromisoformat(d['dato']), skifte=d.get('skifte', ''),
        areal_daa=float(d.get('areal_daa', 0)), gjodseltype=d.get('gjodseltype', ''),
        mengde=float(d.get('mengde', 0)), enhet=d.get('enhet', 'kg'),
        nitrogen_kg=float(d.get('nitrogen_kg', 0)), fosfor_kg=float(d.get('fosfor_kg', 0)),
        kalium_kg=float(d.get('kalium_kg', 0)), metode=d.get('metode', ''),
        vaer=d.get('vaer', ''), notat=d.get('notat', '')
    )
    db.session.add(o)
    db.session.commit()
    return jsonify({"success": True, "id": o.id})


@app.route('/api/gjodseljournal/<int:oid>', methods=['DELETE'])
@login_required
def slett_gjodseljournal(oid):
    o = GjodselJournal.query.get(oid)
    if not o:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404
    db.session.delete(o)
    db.session.commit()
    return jsonify({"success": True})


# --- Sproytejournal ---
@app.route('/api/sproytejournal', methods=['GET'])
@login_required
def hent_sproytejournal():
    q = SproyteJournal.query
    fra = request.args.get('fra')
    til = request.args.get('til')
    if fra:
        q = q.filter(SproyteJournal.dato >= date.fromisoformat(fra))
    if til:
        q = q.filter(SproyteJournal.dato <= date.fromisoformat(til))
    oppf = q.order_by(SproyteJournal.dato.desc()).all()
    return jsonify({"success": True, "data": [{
        "id": o.id, "dato": o.dato.isoformat(), "skifte": o.skifte, "areal_daa": o.areal_daa,
        "preparat": o.preparat, "dose_per_daa": o.dose_per_daa, "total_mengde": o.total_mengde,
        "enhet": o.enhet, "vekst": o.vekst, "skadegjorer": o.skadegjorer,
        "vaer": o.vaer, "temperatur": o.temperatur, "vind": o.vind,
        "behandlingsfrist": o.behandlingsfrist, "notat": o.notat
    } for o in oppf]})


@app.route('/api/sproytejournal', methods=['POST'])
@login_required
def ny_sproytejournal():
    d = request.get_json()
    o = SproyteJournal(
        dato=date.fromisoformat(d['dato']), skifte=d.get('skifte', ''),
        areal_daa=float(d.get('areal_daa', 0)), preparat=d.get('preparat', ''),
        dose_per_daa=float(d.get('dose_per_daa', 0)), total_mengde=float(d.get('total_mengde', 0)),
        enhet=d.get('enhet', 'ml'), vekst=d.get('vekst', ''),
        skadegjorer=d.get('skadegjorer', ''), vaer=d.get('vaer', ''),
        temperatur=float(d['temperatur']) if d.get('temperatur') else None,
        vind=d.get('vind', ''), behandlingsfrist=int(d.get('behandlingsfrist', 0)),
        notat=d.get('notat', '')
    )
    db.session.add(o)
    db.session.commit()
    return jsonify({"success": True, "id": o.id})


@app.route('/api/sproytejournal/<int:oid>', methods=['DELETE'])
@login_required
def slett_sproytejournal(oid):
    o = SproyteJournal.query.get(oid)
    if not o:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404
    db.session.delete(o)
    db.session.commit()
    return jsonify({"success": True})


# --- Dyrehold ---
@app.route('/api/dyrehold', methods=['GET'])
@login_required
def hent_dyrehold():
    q = DyreholdLogg.query
    fra = request.args.get('fra')
    til = request.args.get('til')
    if fra:
        q = q.filter(DyreholdLogg.dato >= date.fromisoformat(fra))
    if til:
        q = q.filter(DyreholdLogg.dato <= date.fromisoformat(til))
    oppf = q.order_by(DyreholdLogg.dato.desc()).all()
    return jsonify({"success": True, "data": [{
        "id": o.id, "dato": o.dato.isoformat(), "dyr_id": o.dyr_id,
        "dyreart": o.dyreart, "hendelse": o.hendelse, "beskrivelse": o.beskrivelse,
        "medisin": o.medisin, "tilbakeholdelse_dager": o.tilbakeholdelse_dager,
        "veteriner": o.veteriner
    } for o in oppf]})


@app.route('/api/dyrehold', methods=['POST'])
@login_required
def ny_dyrehold():
    d = request.get_json()
    o = DyreholdLogg(
        dato=date.fromisoformat(d['dato']), dyr_id=d.get('dyr_id', ''),
        dyreart=d.get('dyreart', ''), hendelse=d.get('hendelse', ''),
        beskrivelse=d.get('beskrivelse', ''), medisin=d.get('medisin', ''),
        tilbakeholdelse_dager=int(d.get('tilbakeholdelse_dager', 0)),
        veteriner=d.get('veteriner', '')
    )
    db.session.add(o)
    db.session.commit()
    return jsonify({"success": True, "id": o.id})


@app.route('/api/dyrehold/<int:oid>', methods=['DELETE'])
@login_required
def slett_dyrehold(oid):
    o = DyreholdLogg.query.get(oid)
    if not o:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404
    db.session.delete(o)
    db.session.commit()
    return jsonify({"success": True})


# --- Vedlikehold ---
@app.route('/api/vedlikehold', methods=['GET'])
@login_required
def hent_vedlikehold():
    q = VedlikeholdsLogg.query
    fra = request.args.get('fra')
    til = request.args.get('til')
    if fra:
        q = q.filter(VedlikeholdsLogg.dato >= date.fromisoformat(fra))
    if til:
        q = q.filter(VedlikeholdsLogg.dato <= date.fromisoformat(til))
    oppf = q.order_by(VedlikeholdsLogg.dato.desc()).all()
    return jsonify({"success": True, "data": [{
        "id": o.id, "dato": o.dato.isoformat(), "maskin": o.maskin,
        "type_vedlikehold": o.type_vedlikehold, "beskrivelse": o.beskrivelse,
        "kostnad": o.kostnad, "utfort_av": o.utfort_av,
        "neste_service": o.neste_service.isoformat() if o.neste_service else ''
    } for o in oppf]})


@app.route('/api/vedlikehold', methods=['POST'])
@login_required
def ny_vedlikehold():
    d = request.get_json()
    o = VedlikeholdsLogg(
        dato=date.fromisoformat(d['dato']), maskin=d.get('maskin', ''),
        type_vedlikehold=d.get('type_vedlikehold', ''), beskrivelse=d.get('beskrivelse', ''),
        kostnad=float(d.get('kostnad', 0)), utfort_av=d.get('utfort_av', ''),
        neste_service=date.fromisoformat(d['neste_service']) if d.get('neste_service') else None
    )
    db.session.add(o)
    db.session.commit()
    return jsonify({"success": True, "id": o.id})


@app.route('/api/vedlikehold/<int:oid>', methods=['DELETE'])
@login_required
def slett_vedlikehold(oid):
    o = VedlikeholdsLogg.query.get(oid)
    if not o:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404
    db.session.delete(o)
    db.session.commit()
    return jsonify({"success": True})


# --- Avfall ---
@app.route('/api/avfall', methods=['GET'])
@login_required
def hent_avfall():
    q = AvfallsLogg.query
    fra = request.args.get('fra')
    til = request.args.get('til')
    if fra:
        q = q.filter(AvfallsLogg.dato >= date.fromisoformat(fra))
    if til:
        q = q.filter(AvfallsLogg.dato <= date.fromisoformat(til))
    oppf = q.order_by(AvfallsLogg.dato.desc()).all()
    return jsonify({"success": True, "data": [{
        "id": o.id, "dato": o.dato.isoformat(), "avfallstype": o.avfallstype,
        "mengde": o.mengde, "enhet": o.enhet, "mottaker": o.mottaker, "notat": o.notat
    } for o in oppf]})


@app.route('/api/avfall', methods=['POST'])
@login_required
def ny_avfall():
    d = request.get_json()
    o = AvfallsLogg(
        dato=date.fromisoformat(d['dato']), avfallstype=d.get('avfallstype', ''),
        mengde=float(d.get('mengde', 0)), enhet=d.get('enhet', 'kg'),
        mottaker=d.get('mottaker', ''), notat=d.get('notat', '')
    )
    db.session.add(o)
    db.session.commit()
    return jsonify({"success": True, "id": o.id})


@app.route('/api/avfall/<int:oid>', methods=['DELETE'])
@login_required
def slett_avfall(oid):
    o = AvfallsLogg.query.get(oid)
    if not o:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404
    db.session.delete(o)
    db.session.commit()
    return jsonify({"success": True})


# --- Oppsynslogg ---
@app.route('/api/oppsynslogg', methods=['GET'])
@login_required
def hent_oppsynslogg():
    q = Oppsynslogg.query
    fra = request.args.get('fra')
    til = request.args.get('til')
    if fra:
        q = q.filter(Oppsynslogg.dato >= date.fromisoformat(fra))
    if til:
        q = q.filter(Oppsynslogg.dato <= date.fromisoformat(til))
    oppf = q.order_by(Oppsynslogg.dato.desc()).all()
    return jsonify({"success": True, "data": [{
        "id": o.id, "dato": o.dato.isoformat(), "sted": o.sted,
        "km_tur_retur": o.km_tur_retur, "timer": o.timer,
        "antall_dyr_sett": o.antall_dyr_sett, "observasjoner": o.observasjoner
    } for o in oppf]})


@app.route('/api/oppsynslogg', methods=['POST'])
@login_required
def ny_oppsynslogg():
    d = request.get_json()
    o = Oppsynslogg(
        dato=date.fromisoformat(d['dato']), sted=d.get('sted', ''),
        km_tur_retur=float(d.get('km_tur_retur', 0)), timer=float(d.get('timer', 0)),
        antall_dyr_sett=int(d.get('antall_dyr_sett', 0)),
        observasjoner=d.get('observasjoner', '')
    )
    db.session.add(o)
    db.session.commit()
    return jsonify({"success": True, "id": o.id})


@app.route('/api/oppsynslogg/<int:oid>', methods=['DELETE'])
@login_required
def slett_oppsynslogg(oid):
    o = Oppsynslogg.query.get(oid)
    if not o:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404
    db.session.delete(o)
    db.session.commit()
    return jsonify({"success": True})


@app.route('/api/oppsynslogg/oppsummering', methods=['GET'])
@login_required
def oppsynslogg_oppsummering():
    periode = request.args.get('periode', 'sesong')
    i_dag = date.today()
    if periode == 'dag':
        start = i_dag
    elif periode == 'uke':
        start = i_dag - timedelta(days=i_dag.weekday())
    elif periode == 'maaned':
        start = i_dag.replace(day=1)
    else:  # sesong (1. mai - 31. okt)
        if i_dag.month >= 5:
            start = i_dag.replace(month=5, day=1)
        else:
            start = i_dag.replace(year=i_dag.year - 1, month=5, day=1)
    oppf = Oppsynslogg.query.filter(Oppsynslogg.dato >= start).all()
    return jsonify({"success": True, "periode": periode, "fra": start.isoformat(), "oppsummering": {
        "antall_turer": len(oppf),
        "total_km": sum(o.km_tur_retur for o in oppf),
        "total_timer": sum(o.timer for o in oppf),
        "total_dyr_sett": sum(o.antall_dyr_sett for o in oppf),
    }})


# --- Kjorebok ---
@app.route('/api/kjorebok', methods=['GET'])
@login_required
def hent_kjorebok():
    q = Kjorebok.query
    fra = request.args.get('fra')
    til = request.args.get('til')
    if fra:
        q = q.filter(Kjorebok.dato >= date.fromisoformat(fra))
    if til:
        q = q.filter(Kjorebok.dato <= date.fromisoformat(til))
    oppf = q.order_by(Kjorebok.dato.desc()).all()
    return jsonify({"success": True, "data": [{
        "id": o.id, "dato": o.dato.isoformat(), "formaal": o.formaal,
        "fra_sted": o.fra_sted, "til_sted": o.til_sted,
        "km_start": o.km_start, "km_slutt": o.km_slutt, "distanse": o.distanse,
        "type_kjoering": o.type_kjoering, "notat": o.notat
    } for o in oppf]})


@app.route('/api/kjorebok', methods=['POST'])
@login_required
def ny_kjorebok():
    d = request.get_json()
    o = Kjorebok(
        dato=date.fromisoformat(d['dato']), formaal=d.get('formaal', ''),
        fra_sted=d.get('fra_sted', ''), til_sted=d.get('til_sted', ''),
        km_start=float(d.get('km_start', 0)), km_slutt=float(d.get('km_slutt', 0)),
        distanse=float(d.get('distanse', 0)), type_kjoering=d.get('type_kjoering', 'gaard'),
        notat=d.get('notat', '')
    )
    db.session.add(o)
    db.session.commit()
    return jsonify({"success": True, "id": o.id})


@app.route('/api/kjorebok/<int:oid>', methods=['DELETE'])
@login_required
def slett_kjorebok(oid):
    o = Kjorebok.query.get(oid)
    if not o:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404
    db.session.delete(o)
    db.session.commit()
    return jsonify({"success": True})


@app.route('/api/kjorebok/oppsummering', methods=['GET'])
@login_required
def kjorebok_oppsummering():
    periode = request.args.get('periode', 'maaned')
    i_dag = date.today()
    if periode == 'maaned':
        start = i_dag.replace(day=1)
    else:  # aar
        start = i_dag.replace(month=1, day=1)
    oppf = Kjorebok.query.filter(Kjorebok.dato >= start).all()
    gaard_km = sum(o.distanse for o in oppf if o.type_kjoering == 'gaard')
    privat_km = sum(o.distanse for o in oppf if o.type_kjoering == 'privat')
    return jsonify({"success": True, "periode": periode, "fra": start.isoformat(), "oppsummering": {
        "antall_turer": len(oppf),
        "total_km": gaard_km + privat_km,
        "gaard_km": gaard_km,
        "privat_km": privat_km,
    }})


# ============================================================================
# API
# ============================================================================

@app.route('/api/sjekklister', methods=['GET'])
def hent_sjekklister():
    return jsonify({"success": True, "sjekklister": {
        k: {"navn": v["navn"], "ikon": v["ikon"], "farge": v["farge"], "antall_punkter": len(v["punkter"])}
        for k, v in SJEKKLISTER.items()
    }})


@app.route('/api/sjekkliste/<sjekkliste_type>', methods=['GET'])
def hent_sjekkliste(sjekkliste_type):
    sl = SJEKKLISTER.get(sjekkliste_type)
    if not sl:
        return jsonify({"success": False, "error": "Sjekkliste ikke funnet"}), 404
    return jsonify({"success": True, "sjekkliste": sl})


@app.route('/api/revisjon/start', methods=['POST'])
def start_revisjon():
    data = request.get_json()
    r = Revisjon(
        gaard_id=data.get('gaard_id', 1),
        sjekkliste_type=data['sjekkliste_type'],
    )
    db.session.add(r)
    db.session.commit()
    return jsonify({"success": True, "revisjon_id": r.id})


@app.route('/api/revisjon/<int:rev_id>/svar', methods=['POST'])
def lagre_svar(rev_id):
    data = request.get_json()
    # Sjekk om svar allerede finnes
    eksisterende = SjekklisteSvar.query.filter_by(revisjon_id=rev_id, punkt_id=data['punkt_id']).first()
    if eksisterende:
        eksisterende.svar = data['svar']
        eksisterende.kommentar = data.get('kommentar', '')
        eksisterende.besvart = datetime.now()
    else:
        s = SjekklisteSvar(
            revisjon_id=rev_id,
            punkt_id=data['punkt_id'],
            svar=data['svar'],
            kommentar=data.get('kommentar', ''),
        )
        db.session.add(s)
    db.session.commit()
    return jsonify({"success": True})


@app.route('/api/revisjon/<int:rev_id>/svar', methods=['GET'])
def hent_svar(rev_id):
    svar = SjekklisteSvar.query.filter_by(revisjon_id=rev_id).all()
    return jsonify({
        "success": True,
        "svar": {s.punkt_id: {"svar": s.svar, "kommentar": s.kommentar} for s in svar}
    })


@app.route('/api/revisjon/<int:rev_id>/fullfoor', methods=['POST'])
def fullfoor_revisjon(rev_id):
    data = request.get_json()
    r = Revisjon.query.get(rev_id)
    if not r:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404

    svar = SjekklisteSvar.query.filter_by(revisjon_id=rev_id).all()
    r.antall_ok = sum(1 for s in svar if s.svar == 'ok')
    r.antall_avvik = sum(1 for s in svar if s.svar == 'avvik')
    r.antall_ir = sum(1 for s in svar if s.svar == 'ir')
    r.status = 'fullfort'
    r.signert_av = data.get('signert_av', '')
    r.signert_dato = datetime.now()
    db.session.commit()

    return jsonify({"success": True, "ok": r.antall_ok, "avvik": r.antall_avvik, "ir": r.antall_ir})


@app.route('/api/revisjoner', methods=['GET'])
def hent_revisjoner():
    revisjoner = Revisjon.query.order_by(Revisjon.opprettet.desc()).all()
    return jsonify({
        "success": True,
        "revisjoner": [{
            "id": r.id,
            "sjekkliste_type": r.sjekkliste_type,
            "sjekkliste_navn": SJEKKLISTER.get(r.sjekkliste_type, {}).get('navn', ''),
            "status": r.status,
            "antall_ok": r.antall_ok,
            "antall_avvik": r.antall_avvik,
            "antall_ir": r.antall_ir,
            "signert_av": r.signert_av,
            "dato": r.opprettet.strftime('%d.%m.%Y %H:%M') if r.opprettet else '',
        } for r in revisjoner]
    })


@app.route('/api/bilde/last-opp', methods=['POST'])
def last_opp_bilde():
    if 'bilde' not in request.files:
        return jsonify({"success": False, "error": "Ingen fil"}), 400
    fil = request.files['bilde']
    if fil.filename == '':
        return jsonify({"success": False, "error": "Tom fil"}), 400

    os.makedirs('static/bilder', exist_ok=True)
    filnavn = f"{uuid.uuid4().hex[:8]}_{fil.filename}"
    sti = os.path.join('static/bilder', filnavn)
    fil.save(sti)

    # Oppdater svar med bilde
    rev_id = request.form.get('revisjon_id')
    punkt_id = request.form.get('punkt_id')
    if rev_id and punkt_id:
        svar = SjekklisteSvar.query.filter_by(revisjon_id=rev_id, punkt_id=punkt_id).first()
        if svar:
            svar.bilde_sti = sti
            db.session.commit()

    return jsonify({"success": True, "sti": sti})


# ============================================================================
# PDF RAPPORT
# ============================================================================

@app.route('/api/revisjon/<int:rev_id>/pdf', methods=['GET'])
@login_required
def generer_revisjon_pdf(rev_id):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER
    from io import BytesIO

    rev = Revisjon.query.get(rev_id)
    if not rev:
        return jsonify({"success": False, "error": "Ikke funnet"}), 404

    gaard = Gaard.query.get(rev.gaard_id)
    sl = SJEKKLISTER.get(rev.sjekkliste_type, {})
    svar_liste = SjekklisteSvar.query.filter_by(revisjon_id=rev_id).all()
    svar_map = {s.punkt_id: s for s in svar_liste}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle('Logo', parent=styles['Heading1'], fontSize=24,
        textColor=colors.HexColor('#2e7d32'), alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle('LogoSub', parent=styles['Normal'], fontSize=10,
        textColor=colors.HexColor('#666666'), alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle('SectionH', parent=styles['Heading2'], fontSize=13,
        textColor=colors.HexColor('#2e7d32'), spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=12))
    styles.add(ParagraphStyle('Small', parent=styles['Normal'], fontSize=7,
        textColor=colors.HexColor('#999999')))

    story = []

    # Logo
    story.append(Paragraph("Gaardsbruk", styles['Logo']))
    story.append(Paragraph("Digital kvalitetsstyring for gardsbruk", styles['LogoSub']))
    story.append(Spacer(1, 0.5*cm))

    # Tittel
    story.append(Paragraph(f"REVISJONSRAPPORT: {sl.get('navn', rev.sjekkliste_type)}", styles['SectionH']))
    story.append(Spacer(1, 0.3*cm))

    # Prosjektinfo
    info_data = [
        ['Gaard:', gaard.navn if gaard else 'Ukjent'],
        ['Adresse:', gaard.adresse if gaard else ''],
        ['Org.nr:', gaard.org_nr if gaard else ''],
        ['Sjekkliste:', sl.get('navn', '')],
        ['Dato:', rev.opprettet.strftime('%d.%m.%Y %H:%M') if rev.opprettet else ''],
        ['Signert av:', rev.signert_av or 'Ikke signert'],
        ['Status:', 'Fullfoert' if rev.status == 'fullfort' else 'Paagaar'],
    ]
    t = Table(info_data, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([
        ('FONT', (0,0), (0,-1), 'Helvetica-Bold', 9),
        ('FONT', (1,0), (1,-1), 'Helvetica', 9),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#2e7d32')),
        ('LINEBELOW', (0,0), (-1,-1), 0.3, colors.HexColor('#e0e0e0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # Oppsummering
    story.append(Paragraph("OPPSUMMERING", styles['SectionH']))
    opps_data = [
        ['Status', 'Antall'],
        ['OK', str(rev.antall_ok)],
        ['Avvik', str(rev.antall_avvik)],
        ['Ikke relevant', str(rev.antall_ir)],
        ['Totalt', str(rev.antall_ok + rev.antall_avvik + rev.antall_ir)],
    ]
    t2 = Table(opps_data, colWidths=[8*cm, 4*cm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2e7d32')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 9),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#e8f5e9')),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#ffebee')),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor('#f5f5f5')),
        ('FONT', (0,1), (-1,-1), 'Helvetica', 9),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#c0c8d0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.5*cm))

    # Detaljerte svar
    story.append(Paragraph("DETALJERTE SVAR", styles['SectionH']))
    for punkt in sl.get('punkter', []):
        svar = svar_map.get(punkt['id'])
        svar_tekst = svar.svar.upper() if svar else 'IKKE BESVART'
        kommentar = svar.kommentar if svar and svar.kommentar else ''

        if svar_tekst == 'OK':
            svar_farge = colors.HexColor('#2e7d32')
        elif svar_tekst == 'AVVIK':
            svar_farge = colors.HexColor('#c62828')
        else:
            svar_farge = colors.HexColor('#999999')

        rad = [[
            Paragraph(f"<b>{punkt['id']}</b>", styles['Body']),
            Paragraph(punkt['tekst'], styles['Body']),
            Paragraph(f"<b><font color='{svar_farge.hexval()}'>{svar_tekst}</font></b>", styles['Body']),
        ]]
        t3 = Table(rad, colWidths=[1.5*cm, 11*cm, 3.5*cm])
        t3.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LINEBELOW', (0,0), (-1,-1), 0.3, colors.HexColor('#eeeeee')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t3)

        if kommentar:
            story.append(Paragraph(f"<i>Kommentar: {kommentar}</i>", ParagraphStyle(
                'Kommentar', parent=styles['Body'], fontSize=8, textColor=colors.HexColor('#c62828'),
                leftIndent=1.5*cm, spaceAfter=4)))

    # Signatur
    story.append(Spacer(1, 1*cm))
    if rev.signert_av:
        story.append(Paragraph(
            f"<b>Signert av:</b> {rev.signert_av} | "
            f"<b>Dato:</b> {rev.signert_dato.strftime('%d.%m.%Y %H:%M') if rev.signert_dato else ''}",
            styles['Body']))

    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        "Denne rapporten er generert av Gaardsbruk - Digital kvalitetsstyring for gardsbruk.",
        styles['Small']))

    doc.build(story)
    buf.seek(0)

    return send_file(
        buf, mimetype='application/pdf', as_attachment=True,
        download_name=f"Revisjon_{rev.sjekkliste_type}_{rev.opprettet.strftime('%Y%m%d') if rev.opprettet else ''}.pdf"
    )


if __name__ == '__main__':
    app.run(debug=True, port=5002)
