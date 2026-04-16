from flask import Blueprint, jsonify, request

from devteam_demo.auth.login import login, logout, InvalidCredentialsError
from devteam_demo.auth.two_factor import verify_two_factor, InvalidTwoFactorCodeError


bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.post('/login')
def login_endpoint():
    payload = request.get_json() or {}
    try:
        token = login(payload.get('username', ''), payload.get('password', ''))
    except InvalidCredentialsError:
        return jsonify(error='invalid_credentials'), 401
    return jsonify(session_token=token)


@bp.post('/logout')
def logout_endpoint():
    token = request.headers.get('X-Session-Token', '')
    logout(token)
    return '', 204


@bp.post('/two-factor/verify')
def verify_two_factor_endpoint():
    token = request.headers.get('X-Session-Token', '')
    payload = request.get_json() or {}
    try:
        verify_two_factor(token, payload.get('code', ''))
    except InvalidTwoFactorCodeError:
        return jsonify(error='invalid_code'), 401
    return jsonify(status='ok')
