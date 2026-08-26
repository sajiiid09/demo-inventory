"""Member rules — TESTING.md §3 subset."""

from tests.conftest import make_loan, make_member, unique


class TestMembers:
    def test_create_member_assigns_sequential_member_code(self, clients, db):
        from app.models import Member
        from sqlalchemy import func, select

        member = make_member(clients)
        # the code is sequential relative to whatever exists in the test DB
        count = db.scalar(select(func.count()).select_from(Member))
        expected_number = member["member_code"].split("-")[1]
        assert int(expected_number) <= count

    def test_duplicate_phone_returns_409_duplicate_field(self, clients):
        first = make_member(clients)
        response = clients.officer.post(
            "/members", json=unique(phone=first["phone"])
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "DUPLICATE_FIELD"

    def test_duplicate_national_id_returns_409_duplicate_field(self, clients):
        first = make_member(clients)
        response = clients.officer.post(
            "/members", json=unique(national_id=first["national_id"])
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "DUPLICATE_FIELD"

    def test_search_matches_partial_name_phone_and_member_code(self, clients):
        from tests.conftest import unique
        import uuid

        marker = uuid.uuid4().hex[:8]
        member = make_member(
            clients, full_name=f"Searchable {marker}", phone=f"016{marker}777"
        )
        for q in (marker, marker[:4], member["member_code"]):
            response = clients.officer.get(f"/members?q={q}")
            codes = [i["member_code"] for i in response.json()["items"]]
            assert member["member_code"] in codes

    def test_cannot_deactivate_member_with_active_loan(self, clients):
        loan = make_loan(clients)  # DISBURSED
        response = clients.admin.patch(
            f"/members/{loan['member']['id']}/status", json={"status": "INACTIVE"}
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "INVALID_STATE"

    def test_member_detail_includes_full_loan_history(self, clients):
        loan = make_loan(clients)
        response = clients.officer.get(f"/members/{loan['member']['id']}")
        history = response.json()["loans"]
        assert [l["loan_code"] for l in history] == [loan["loan_code"]]
        assert history[0]["status"] == "DISBURSED"
        assert history[0]["outstanding"] == loan["totals"]["total_payable"]
