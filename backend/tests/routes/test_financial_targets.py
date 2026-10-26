"""三種對象、活動合併與家庭長期目標的整合驗收。"""
from datetime import timedelta

import pytest

from app.models import Advice, Allowance, Category, Family, FamilyMember, Transaction
from app.toolkit import crud
from tests.routes.conftest import categories, family_of, guard, ledger_of, login, now, spend, today, user


def personal(who):
    return ledger_of(who, name=who.display_name + '的帳本', personal_owner_id=who.id)


@pytest.mark.route('GET', '/api/summary')
def test_live_activity_pocket_income_does_not_reduce_personal_allowance(api):
    dad, kid = user('dad@x.tw', '爸爸'), user('kid@x.tw', '孩子')
    family_of((dad, 'parent'), (kid, 'child'))
    guard(dad, kid)
    personal(kid)
    category = crud.save(Category, {'name': '零用金', 'kind': 'income', 'color': 'cat-other'})
    crud.save(Allowance, {'payer_id': dad.id, 'ward_id': kid.id, 'amount': 3000})
    activity = ledger_of(kid, dad)
    spend(kid, activity, category, 1000)
    before = api.get('/api/summary', headers=login(kid)).json()
    # 零用金已經自動入帳 3,000；活動裡那 1,000 還沒合併，不算進個人
    assert (before['income'], before['pocketMoney'], before['savings']['allowance']) == (3000, 0, 3000)
    assert api.post('/api/groups/' + str(activity.id) + '/settle', headers=login(kid)).status_code == 200
    after = api.get('/api/summary', headers=login(kid)).json()
    assert (after['income'], after['pocketMoney'], after['savings']['allowance']) == (4000, 0, 4000)


@pytest.mark.route('GET', '/api/summary')
def test_targets_exclude_live_activities_and_keep_departed_activity_records(api):
    dad, mom, kid, friend = [user(n + '@x.tw', n) for n in ('dad', 'mom', 'kid', 'friend')]
    family_of((dad, 'parent'), (mom, 'parent'), (kid, 'child'))
    cats = categories()
    pd, pm, pk = personal(dad), personal(mom), personal(kid)
    spend(dad, pd, cats['薪資'], 10000)
    spend(mom, pm, cats['餐飲'], 200)
    spend(kid, pk, cats['其他收入'], 3000)
    spend(kid, pk, cats['餐飲'], 100)
    activity = ledger_of(dad, friend, name='朋友活動')
    original = spend(friend, activity, cats['餐飲'], 700)
    spend(dad, activity, cats['餐飲'], 500)
    h = login(dad)
    assert api.get('/api/summary', headers=h).json()['expense'] == 0
    fam = api.get('/api/summary?scope=family&groupId=' + str(activity.id), headers=h).json()
    assert (fam['income'], fam['expense'], fam['count']) == (10000, 300, 4)
    active = api.get('/api/summary?groupId=' + str(activity.id), headers=h).json()
    assert active['expense'] == 1200 and len(active['members']) == 2
    assert api.post('/api/groups/' + str(activity.id) + '/settle', headers=login(friend)).status_code == 200
    assert crud.get(Transaction, original.id).group_id == activity.id
    assert api.get('/api/summary?groupId=' + str(activity.id), headers=h).json()['expense'] == 1200
    assert api.get('/api/summary', headers=login(friend)).json()['expense'] == 700
    assert api.get('/api/summary', headers=h).json()['expense'] == 0
    assert api.post('/api/groups/' + str(activity.id) + '/settle', headers=h).status_code == 200
    assert api.get('/api/summary', headers=h).json()['expense'] == 500


@pytest.mark.route('GET', '/api/transactions/archive')
def test_family_detail_permissions_and_activity_origin_survive_archive(api):
    dad, kid = user('dad@x.tw', '爸爸'), user('kid@x.tw', '孩子')
    family_of((dad, 'parent'), (kid, 'child'))
    cats = categories()
    pd, pk = personal(dad), personal(kid)
    spend(dad, pd, cats['薪資'], 10000)
    ktx = spend(kid, pk, cats['餐飲'], 150)
    activity = ledger_of(dad, kid)
    spend(kid, activity, cats['餐飲'], 888)
    h = login(dad)
    rows = api.get('/api/transactions?scope=family', headers=h).json()['transactions']
    assert str(ktx.id) not in {t['id'] for t in rows}
    guard(dad, kid)
    rows = api.get('/api/transactions?scope=family', headers=h).json()['transactions']
    assert {t['amount'] for t in rows} == {10000, 150}
    archive = api.get('/api/transactions/archive?scope=family', headers=h).json()
    assert sum(m['count'] for y in archive['years'] for m in y['months']) == 2
    assert api.get('/api/transactions?groupId=' + str(pd.id), headers=login(kid)).status_code == 403
    for endpoint in ('/summary', '/advices', '/transactions', '/transactions/archive', '/budgets'):
        assert api.get('/api' + endpoint + '?scope=family', headers=login(kid)).status_code == 403


@pytest.mark.route('PATCH', '/api/family')
def test_family_goal_parent_permissions_and_cumulative_progress(api):
    dad, kid = user('dad@x.tw', '爸爸'), user('kid@x.tw', '孩子')
    h = login(dad)
    created = api.post('/api/family', headers=h, json={'name': '測試家庭', 'goalAmount': 10000, 'goalNote': '旅行基金'})
    assert created.status_code == 201, created.text
    fid = int(created.json()['family']['id'])
    crud.save(Family, {'id': fid, 'created_at': now() - timedelta(days=10)})
    crud.save(FamilyMember, {'family_id': fid, 'user_id': kid.id, 'role': 'child'})
    cats = categories()
    pd, pk = personal(dad), personal(kid)
    spend(dad, pd, cats['薪資'], 5000)
    spend(dad, pd, cats['餐飲'], 500)
    spend(kid, pk, cats['其他收入'], 3000)
    spend(kid, pk, cats['餐飲'], 200)
    live = ledger_of(dad)
    spend(dad, live, cats['餐飲'], 999)
    result = api.get('/api/family', headers=h).json()['family']['goal']
    assert (result['amount'], result['note'], result['accumulated'], result['ratio']) == (10000, '旅行基金', 4300, .43)
    changed = api.patch('/api/family', headers=h, json={'goalAmount': 20000, 'goalNote': '全家旅行'}).json()['family']['goal']
    assert changed['since'] == result['since'] and changed['accumulated'] == 4300
    assert changed['remaining'] == 15700
    assert api.patch('/api/family', headers=login(kid), json={'goalAmount': 1}).status_code == 403
    for body in ({'goalAmount': -1}, {'goalAmount': 1.234}, {'goalAmount': 1, 'goalNote': '字' * 301}, {'goalAmount': 1, 'name': '偷改'}):
        assert api.patch('/api/family', headers=h, json=body).status_code == 422


@pytest.mark.route('POST', '/api/advices/generate')
def test_advice_target_storage_and_family_goal_prompt(api, monkeypatch):
    from app.services.llm import advice
    dad, friend = user('dad@x.tw', '爸爸'), user('friend@x.tw', '朋友')
    fam = family_of((dad, 'parent'))
    crud.save(Family, {'id': fam.id, 'goal_amount': 50000, 'goal_note': '全家旅行'})
    cats = categories()
    pd = personal(dad)
    spend(dad, pd, cats['餐飲'], 100)
    activity = ledger_of(dad, friend, name='登山活動')
    spend(friend, activity, cats['餐飲'], 800)
    calls = []
    def fake(numbers, block):
        calls.append((numbers, block))
        return [{'level': 'info', 'title': '記帳建議', 'body': '維持記帳習慣', 'basis': ['依據本月已入帳紀錄'], 'suggest': [], 'conf': .9}]
    monkeypatch.setattr(advice, 'write_advices', fake)
    h = login(dad)
    for body in ({'scope': 'me'}, {'scope': 'me', 'groupId': str(activity.id)}, {'scope': 'family'}):
        response = api.post('/api/advices/generate', headers=h, json=body)
        assert response.status_code == 201, response.text
    assert [c[0]['expense'] for c in calls] == [100, 800, 100]
    assert calls[2][0]['familyGoal']['amount'] == 50000 and '全家旅行' in calls[2][1]
    assert crud.count(Advice) == 3
    assert len(api.get('/api/advices', headers=h).json()['advices']) == 1
    active = api.get('/api/advices?groupId=' + str(activity.id), headers=h).json()['advices']
    assert len(active) == 1
    assert len(api.get('/api/advices?scope=family', headers=h).json()['advices']) == 1
    # 家庭只有建立者，也可以立即取得家庭摘要與建議。
    assert api.get('/api/summary?scope=family', headers=h).status_code == 200
