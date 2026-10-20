import json
d = json.load(open(r'D:\.0WORK\GiteeCode\dne-code\IPE\tools\ipe-stats\samples\r2026x_w18.3.json', encoding='utf-8'))

print('=== role_availability axis ===')
for it in d['axes']['role_availability']:
    print(f'  id={it["id"]} | name={it["name"]}')

# 拿 GA/CA 的真实 id
ra_map = {r["id"]: r["name"].upper() for r in d['axes']['role_availability']}
ga_ids = {i for i, n in ra_map.items() if n == "GA"}
ca_ids = {i for i, n in ra_map.items() if n == "CA"}
print(f'\nGA ids: {ga_ids}')
print(f'CA ids: {ca_ids}')

# 看 croles children 里有多少含 GA
croles_children = [it for it in d['items'] if it.get('axis_origin')=='croles' and it.get('croline_group') and it['id']!=it.get('croline_group')]
ga_count = sum(1 for it in croles_children if (set(it.get('compat_with') or []) & ga_ids))
ca_count = sum(1 for it in croles_children if (set(it.get('compat_with') or []) & ca_ids))
print(f'\n=== Croles children GA/CA 统计 ===')
print(f'  total: {len(croles_children)}')
print(f'  with GA: {ga_count}')
print(f'  with CA: {ca_count}')

# 看 IPE GA 统计
ipe = d['axes']['ipe']
ipe_ga = [it for it in ipe if (set(it.get('compat_with') or []) & ga_ids)]
print(f'\n=== IPE GA 统计 ===')
print(f'  total: {len(ipe)}, GA: {len(ipe_ga)}')

# Portfolio
pf = d['axes']['portfolios']
pf_ga = [it for it in pf if (set(it.get('compat_with') or []) & ga_ids)]
print(f'\n=== Portfolio GA 统计 ===')
print(f'  total: {len(pf)}, GA: {len(pf_ga)}')

# ISE
ise = d['axes'].get('ise', [])
ise_ga = [it for it in ise if (set(it.get('compat_with') or []) & ga_ids)]
print(f'\n=== ISE GA 统计 ===')
print(f'  total: {len(ise)}, GA: {len(ise_ga)}')

# Industry Portfolio
ip = d['axes'].get('industry_portfolios', [])
ip_ga = [it for it in ip if (set(it.get('compat_with') or []) & ga_ids)]
print(f'\n=== Industry Portfolio GA 统计 ===')
print(f'  total: {len(ip)}, GA: {len(ip_ga)}')
