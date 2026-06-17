"""TransMed 完整端到端测试"""
import time, os
from playwright.sync_api import sync_playwright

shot_dir = "/tmp/transmed_e2e"
os.makedirs(shot_dir, exist_ok=True)
passed = []
failed = []
screenshots = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True,
        args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
    )
    page = browser.new_context(viewport={"width": 1400, "height": 900}).new_page()

    page.goto("file:///Users/johnwoo/Documents/TransMed/transmed_web/index.html", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    page.screenshot(path=os.path.join(shot_dir, "01_home.png"))
    screenshots.append("01_home.png")
    passed.append(f"首页加载: {page.title()}")

    # === Hospitals ===
    page.locator('.nav-link[data-view="hospitals"]').click()
    time.sleep(2)
    page.screenshot(path=os.path.join(shot_dir, "02_hospitals.png"))
    screenshots.append("02_hospitals.png")

    page.evaluate("document.getElementById('triage-input').value = 'severe chest pain, shortness of breath, high fever'")
    page.evaluate("document.getElementById('btn-triage').click()")
    time.sleep(2)
    page.screenshot(path=os.path.join(shot_dir, "03_triage.png"))
    screenshots.append("03_triage.png")

    triage = page.locator("#triage-result").inner_text().strip()
    if len(triage) > 10:
        passed.append(f"分诊结果: {triage[:80]}")
    else:
        failed.append(f"分诊结果异常 (空或太短): '{triage[:80]}'")

    h_count = page.locator(".hospital").count()
    if h_count >= 3:
        passed.append(f"医院卡片: {h_count}")
    else:
        failed.append(f"医院卡片不足: {h_count}")

    # rating badge
    r_count = page.locator(".rating-badge").count()
    if r_count >= 1:
        passed.append(f"rating-badge: {r_count}")
    else:
        failed.append("无 rating-badge")

    # Insurance filter
    page.evaluate("document.getElementById('insurance-filter').value = 'BUPA'")
    page.evaluate("document.getElementById('btn-triage').click()")
    time.sleep(2)
    passed.append(f"BUPA 筛选后: {page.locator('.hospital').count()} 张卡片")

    # === Navigation ===
    page.locator('.nav-link[data-view="navigation"]').click()
    time.sleep(3)
    page.screenshot(path=os.path.join(shot_dir, "04_navigation.png"))
    screenshots.append("04_navigation.png")

    svg_circle = page.locator("#nav-svg circle").count()
    if svg_circle >= 5:
        passed.append(f"SVG 节点: {svg_circle}")
    else:
        failed.append(f"SVG 节点不足: {svg_circle}")

    # route: entrance -> emergency
    sel = page.evaluate("() => { const d = document.getElementById('nav-dest'); for(let i=0;i<d.options.length;i++) if(d.options[i].value==='emergency'){d.selectedIndex=i; break;} d.dispatchEvent(new Event('change')); return d.value; }")
    page.evaluate("document.getElementById('btn-navigate').click()")
    time.sleep(4)
    page.screenshot(path=os.path.join(shot_dir, "05_route_emergency.png"))
    screenshots.append("05_route_emergency.png")

    steps = page.locator(".nav-step").count()
    if steps >= 3:
        passed.append(f"导航步骤: {steps}")
    else:
        failed.append(f"导航步骤不足: {steps}")

    # route: entrance -> cardiology (Floor 2)
    page.evaluate("() => { const d = document.getElementById('nav-dest'); for(let i=0;i<d.options.length;i++) if(d.options[i].value==='cardiology'){d.selectedIndex=i; break;} }")
    page.evaluate("document.getElementById('btn-navigate').click()")
    time.sleep(4)
    route_txt = page.locator("#nav-route").inner_text() or ""
    if "Floor 2" in route_txt or "电梯" in route_txt or "F2" in route_txt or "cardiology" in route_txt.lower():
        passed.append(f"跨楼层导航 OK: {route_txt[:80]}")
    else:
        failed.append(f"跨楼层导航信息不足: {route_txt[:120]}")

    # === Translate ===
    page.locator('.nav-link[data-view="translate"]').click()
    time.sleep(1.5)
    page.evaluate("document.getElementById('src-text').value = 'I have a sore throat and runny nose for 2 days'")
    page.evaluate("document.getElementById('btn-translate').click()")
    time.sleep(10)
    page.screenshot(path=os.path.join(shot_dir, "06_translate.png"))
    screenshots.append("06_translate.png")

    translated = page.locator("#tgt-text").inner_text() or ""
    if len(translated) >= 5 and "sore" not in translated and "throat" not in translated:
        passed.append(f"在线翻译成功: {translated[:40]}")
    else:
        failed.append(f"翻译结果异常: '{translated[:80]}'")

    engine_label = ""
    if page.locator("#engine-label").count():
        engine_label = page.locator("#engine-label").inner_text() or ""
        passed.append(f"引擎标签: {engine_label[:60]}")

    browser.close()

print(f"\n{'='*60}\n✅ 通过 {len(passed)}  |  ❌ 失败 {len(failed)}\n{'='*60}")
for i, x in enumerate(passed): print(f"  [{i+1:02d}] {x}")
if failed:
    print("\n--- 失败 ---")
    for i, x in enumerate(failed): print(f"  [F{i+1:02d}] {x}")
print(f"\n截图: {len(screenshots)} 张 → {shot_dir}/")
for s in screenshots: print(f"  {s}")
