import re
from functools import wraps
from urllib.parse import unquote, urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import Language, LearnerProfile, User


auth = Blueprint("auth", __name__, url_prefix="/auth")
account = Blueprint("account", __name__, url_prefix="/account")
USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,30}$")
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def load_current_user():
    user_id = session.get("user_id")
    g.current_user = db.session.get(User, user_id) if isinstance(user_id, str) else None
    if user_id is not None and g.current_user is None:
        session.clear()


def inject_current_user():
    return {"current_user": g.get("current_user")}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("current_user") is None:
            return redirect(
                url_for("auth.login", next=request.full_path.rstrip("?"))
            )
        return view(*args, **kwargs)

    return wrapped


def safe_local_next(value):
    if not value or len(value) > 2048 or "\\" in value:
        return None
    decoded = value
    for _ in range(8):
        unescaped = unquote(decoded)
        if unescaped == decoded:
            break
        decoded = unescaped
    else:
        return None
    if decoded.startswith("//") or "\\" in decoded or any(
        ord(character) < 32 or ord(character) == 127 for character in decoded
    ):
        return None
    parsed = urlsplit(decoded)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return None
    if parsed.path.startswith("//"):
        return None
    return value


def _registration_values():
    return {
        "username": request.form.get("username", "").strip(),
        "email": request.form.get("email", "").strip(),
    }


@auth.route("/register", methods=["GET", "POST"])
def register():
    values = _registration_values()
    errors = {}
    if request.method == "POST":
        username = values["username"].lower()
        email = values["email"].casefold()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")

        if not USERNAME_PATTERN.fullmatch(username):
            errors["username"] = (
                "Use 3–30 letters, numbers, or underscores for your username."
            )
        if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
            errors["email"] = "Enter a valid email address."
        if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
            errors["password"] = (
                f"Use a password between {MIN_PASSWORD_LENGTH} and "
                f"{MAX_PASSWORD_LENGTH} characters."
            )
        if confirmation != password:
            errors["confirm_password"] = "The passwords do not match."

        if not errors:
            existing = db.session.scalar(
                select(User).where(
                    or_(User.username == username, User.email == email)
                )
            )
            if existing is not None:
                if existing.username == username:
                    errors["username"] = "That username is already in use."
                if existing.email == email:
                    errors["email"] = "That email address is already in use."

        if not errors:
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.add(LearnerProfile(user=user))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors["form"] = (
                    "An account with that username or email already exists. "
                    "Please review your details."
                )
            else:
                flash(
                    "Your account is ready. Log in to continue.",
                    "success",
                )
                return redirect(url_for("auth.login"))

    return (
        render_template(
            "auth/register.html",
            page="account",
            values=values,
            errors=errors,
        ),
        400 if errors else 200,
    )


@auth.route("/login", methods=["GET", "POST"])
def login():
    next_url = safe_local_next(
        request.form.get("next") if request.method == "POST"
        else request.args.get("next")
    )
    error = None
    identifier = ""
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().casefold()
        password = request.form.get("password", "")
        user = None
        if identifier and len(identifier) <= 254 and 0 < len(password) <= MAX_PASSWORD_LENGTH:
            user = db.session.scalar(
                select(User).where(
                    or_(User.username == identifier, User.email == identifier)
                )
            )
        valid_password = False
        if user is not None and user.password_hash:
            try:
                valid_password = check_password_hash(user.password_hash, password)
            except (TypeError, ValueError):
                current_app.logger.warning(
                    "Stored password hash could not be verified."
                )
        if not valid_password:
            error = "The username/email or password is incorrect."
        else:
            session.clear()
            session["user_id"] = user.id
            session.permanent = True
            flash("You are now logged in.", "success")
            return redirect(next_url or url_for("web.home"))

    return (
        render_template(
            "auth/login.html",
            page="account",
            next_url=next_url,
            identifier=identifier,
            error=error,
        ),
        401 if error else 200,
    )


@auth.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@account.get("/profile")
@login_required
def profile():
    user = g.current_user
    profile_record = user.profile or LearnerProfile(user_id=user.id)
    return render_template(
        "account/profile.html",
        page="account",
        user=user,
        profile=profile_record,
    )


@account.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = g.current_user
    profile_record = user.profile or LearnerProfile(user_id=user.id)
    languages = db.session.scalars(
        select(Language).order_by(Language.position, Language.code)
    ).all()
    errors = {}
    values = {
        "display_name": profile_record.display_name or "",
        "bio": profile_record.bio or "",
        "preferred_language_code": profile_record.preferred_language_code or "",
    }

    if request.method == "POST":
        values = {
            "display_name": request.form.get("display_name", "").strip(),
            "bio": request.form.get("bio", "").strip(),
            "preferred_language_code": request.form.get(
                "preferred_language_code", ""
            ).strip(),
        }
        if len(values["display_name"]) > 80:
            errors["display_name"] = "Display name must be 80 characters or fewer."
        if len(values["bio"]) > 280:
            errors["bio"] = "Bio must be 280 characters or fewer."
        language_codes = {language.code for language in languages}
        if (
            values["preferred_language_code"]
            and values["preferred_language_code"] not in language_codes
        ):
            errors["preferred_language_code"] = (
                "Choose a language from the available list."
            )

        if not errors:
            if user.profile is None:
                profile_record = LearnerProfile(user=user)
                db.session.add(profile_record)
            profile_record.display_name = values["display_name"] or None
            profile_record.bio = values["bio"] or None
            profile_record.preferred_language_code = (
                values["preferred_language_code"] or None
            )
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                current_app.logger.warning(
                    "Learner profile update failed database integrity validation."
                )
                errors["form"] = (
                    "Your changes could not be saved. Please review the form and retry."
                )
            else:
                flash("Your profile settings have been saved.", "success")
                return redirect(url_for("account.profile"))

    return render_template(
        "account/settings.html",
        page="account",
        user=user,
        profile=profile_record,
        languages=languages,
        values=values,
        errors=errors,
    ), 400 if errors else 200
