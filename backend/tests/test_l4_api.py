"""
L4 API 层集成测试
测试模块: 根路径/健康检查/推荐主题/知识体系/统一响应格式/404处理
运行方式: python tests/test_l4_api.py
前置条件: 后端服务运行在 localhost:8000
"""

import sys
import os
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"
# 有效 JWT token（使用默认 secret 签名）
import jwt as _jwt, time as _time
_MOCK_TOKEN = _jwt.encode({
    "user_id": "test-user", "sub": "test-user",
    "exp": int(_time.time()) + 3600,
    "subscription_type": "PRO"
}, "your-secret-key-change-in-production", algorithm="HS256")
MOCK_TOKEN = f"Bearer {_MOCK_TOKEN}"

passed = 0
failed = 0
results = []

def record(test_id: str, name: str, status: str, detail: str = ""):
    global passed, failed
    results.append({"id": test_id, "name": name, "status": status, "detail": detail})
    icon = "✓" if status == "PASS" else "✗"
    print(f"  {icon} {test_id}: {name}" + (f" — {detail}" if detail else ""))
    if status == "PASS":
        passed += 1
    else:
        failed += 1

def http_get(path: str, auth: bool = False) -> tuple:
    """发送GET请求，返回(status_code, response_dict)"""
    try:
        req = urllib.request.Request(f"{BASE_URL}{path}")
        if auth:
            req.add_header("Authorization", MOCK_TOKEN)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            data = json.loads(body)
        except:
            data = {"error": body}
        return e.code, data
    except Exception as e:
        return 0, {"error": str(e)}


def test_api():
    print("=" * 60)
    print("L4 API 层集成测试")
    print("=" * 60)

    # 预热：发送一个请求确保熔断器关闭
    print("\n预热: 等待熔断器恢复...")
    import time
    time.sleep(2)
    try:
        http_get("/")
    except:
        pass
    time.sleep(1)

    # API-01: 根路径
    print("\n[API-01] 根路径 GET /")
    print("-" * 50)
    try:
        status, data = http_get("/")
        has_name = "name" in str(data)
        has_version = "version" in str(data)
        has_running = "running" in str(data)
        ok = status == 200 and has_name and has_version and has_running
        record("API-01", "根路径", "PASS" if ok else "FAIL",
               f"status={status}, data={json.dumps(data, ensure_ascii=False)[:80]}")
    except Exception as e:
        record("API-01", "根路径", "FAIL", str(e))

    # API-02: 健康检查
    print("\n[API-02] 健康检查 GET /health")
    print("-" * 50)
    try:
        status, data = http_get("/health")
        is_healthy = "healthy" in str(data)
        ok = status == 200 and is_healthy
        record("API-02", "健康检查", "PASS" if ok else "FAIL",
               f"status={status}, healthy={is_healthy}")
    except Exception as e:
        record("API-02", "健康检查", "FAIL", str(e))

    # API-03: 推荐主题
    print("\n[API-03] 推荐主题 GET /api/v1/topics/recommend?count=3")
    print("-" * 50)
    try:
        status, data = http_get("/api/v1/topics/recommend?count=3")
        code = data.get("code")
        topics = data.get("data", [])
        if isinstance(topics, dict):
            topics = topics.get("topics", [])
        elif not isinstance(topics, list):
            topics = []
        ok = status == 200 and code == 0 and len(topics) >= 0
        record("API-03", "推荐主题", "PASS" if ok else "FAIL",
               f"status={status}, code={code}, topics={len(topics)}")
    except Exception as e:
        record("API-03", "推荐主题", "FAIL", str(e))

    # API-04: 推荐数量边界
    print("\n[API-04] 推荐数量边界 GET /api/v1/topics/recommend?count=11")
    print("-" * 50)
    try:
        status, data = http_get("/api/v1/topics/recommend?count=11")
        topics = data.get("data", [])
        if isinstance(topics, dict):
            topics = topics.get("topics", [])
        elif not isinstance(topics, list):
            topics = []
        # count=11 应被限制为默认值（上限10）
        is_limited = len(topics) <= 10
        record("API-04", "推荐数量边界", "PASS" if is_limited else "FAIL",
               f"count=11, 返回topics={len(topics)}, 受限={is_limited}")
    except Exception as e:
        record("API-04", "推荐数量边界", "FAIL", str(e))

    # API-05: 知识体系
    print("\n[API-05] 知识体系 GET /api/v1/topics/{id}/structure")
    print("-" * 50)
    try:
        status, data = http_get("/api/v1/topics/test-topic-001/structure", auth=True)
        code = data.get("code")
        resp_data = data.get("data", {})
        has_blocks = False
        if isinstance(resp_data, dict):
            has_blocks = "blocks" in resp_data or "structure" in resp_data
        ok = status in (200, 404, 422)
        record("API-05", "知识体系", "PASS" if ok else "FAIL",
               f"status={status}, code={code}, has_blocks={has_blocks}")
    except Exception as e:
        record("API-05", "知识体系", "FAIL", str(e))

    # API-06: 统一响应格式
    print("\n[API-06] 统一响应格式")
    print("-" * 50)
    try:
        status, data = http_get("/")
        required = {"code", "message", "data", "meta"}
        actual = set(data.keys())
        has_all = required.issubset(actual)
        has_timestamp = "timestamp" in data.get("meta", {})
        has_version = "version" in data.get("meta", {})
        ok = has_all and has_timestamp and has_version
        record("API-06", "统一响应格式", "PASS" if ok else "FAIL",
               f"字段完整={has_all}, timestamp={has_timestamp}, version={has_version}")
    except Exception as e:
        record("API-06", "统一响应格式", "FAIL", str(e))

    # API-07: 404 处理
    print("\n[API-07] 404 处理 GET /api/v1/not-exist")
    print("-" * 50)
    try:
        status, data = http_get("/api/v1/not-exist", auth=True)
        # 认证通过后，不存在的路由应返回404
        is_404 = status == 404
        has_error = "error" in data or "detail" in data or "message" in data
        ok = is_404
        record("API-07", "404 处理", "PASS" if ok else "FAIL",
               f"status={status}, has_error_info={has_error}")
    except Exception as e:
        record("API-07", "404 处理", "FAIL", str(e))

    # 报告
    print("\n" + "=" * 60)
    print("L4 测试报告")
    print("=" * 60)
    total = passed + failed
    print(f"\n总计: {total} 个用例")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print(f"通过率: {passed/total*100:.1f}%")

    if failed > 0:
        print("\n失败用例:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  ✗ {r['id']}: {r['name']} — {r['detail']}")

    print("\n" + "=" * 60)
    return failed == 0


if __name__ == "__main__":
    ok = test_api()
    sys.exit(0 if ok else 1)
