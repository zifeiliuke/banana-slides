from models import db, User, Referral, SystemSettings, PointsBalance


def test_registration_referral_creates_record_and_grants_points(client):
    settings = SystemSettings.get_settings()
    settings.require_email_verification = False
    settings.referral_enabled = True
    db.session.commit()

    inviter_res = client.post(
        "/api/auth/register",
        json={"username": "liuke", "password": "password123"},
    )
    assert inviter_res.status_code == 201

    inviter = User.query.filter_by(username="liuke").first()
    assert inviter is not None
    assert inviter.referral_code

    invitee_res = client.post(
        "/api/auth/register",
        json={
            "username": "jiangtang",
            "password": "password123",
            "referral_code": inviter.referral_code,
        },
    )
    assert invitee_res.status_code == 201

    invitee = User.query.filter_by(username="jiangtang").first()
    assert invitee is not None
    assert invitee.referred_by_user_id == inviter.id

    referral = Referral.query.filter_by(inviter_user_id=inviter.id, invitee_user_id=invitee.id).first()
    assert referral is not None
    assert referral.status == "registered"
    assert referral.register_reward_granted is True
    assert referral.register_reward_days == settings.referral_inviter_register_points

    inviter_reward = PointsBalance.query.filter_by(
        user_id=inviter.id,
        source=PointsBalance.SOURCE_REFERRAL_INVITER_REGISTER,
    ).first()
    assert inviter_reward is not None
    assert inviter_reward.amount == settings.referral_inviter_register_points

    invitee_reward = PointsBalance.query.filter_by(
        user_id=invitee.id,
        source=PointsBalance.SOURCE_REFERRAL_INVITEE_REGISTER,
    ).first()
    assert invitee_reward is not None
    assert invitee_reward.amount == settings.referral_invitee_register_points

