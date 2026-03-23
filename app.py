# ============================================================================
# KSL Digital - Digitale sjekklister for kvalitetsstyring i landbruket
# ============================================================================

from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
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


if __name__ == '__main__':
    app.run(debug=True, port=5002)
