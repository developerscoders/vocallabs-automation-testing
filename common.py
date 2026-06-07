import json
import os
import random
import time
from pathlib import Path
from typing import Any, Callable

import requests
from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data_json"


class ApiError(RuntimeError):
    pass


def load_environment() -> None:
    load_dotenv(PROJECT_DIR / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def api_delay_seconds() -> float:
    raw_value = os.getenv("API_DELAY_SECONDS", "1.0")
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        print(f"Invalid API_DELAY_SECONDS={raw_value!r}; using 1.0 seconds.")
        return 1.0


def pace_api_calls() -> None:
    delay = api_delay_seconds()
    if delay > 0:
        time.sleep(delay)


def load_json(path: str | Path, default: Any = None) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        return default
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: str | Path, payload: Any) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def request_with_retries(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 45,
    max_attempts: int = 4,
    base_delay: float = 2.0,
) -> dict[str, Any]:
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=json_payload,
                params=params,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            if attempt == max_attempts:
                raise ApiError(str(exc)) from exc
            sleep_for = _backoff_delay(base_delay, attempt)
            print(f"Request failed: {exc}. Retrying in {sleep_for:.1f}s...")
            time.sleep(sleep_for)
            continue

        if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < max_attempts:
            retry_after = response.headers.get("Retry-After")
            sleep_for = float(retry_after) if retry_after else _backoff_delay(base_delay, attempt)
            print(f"Rate/server limit ({response.status_code}). Retrying in {sleep_for:.1f}s...")
            time.sleep(sleep_for)
            continue

        if not response.ok:
            message = _response_error_message(response)
            raise ApiError(f"{response.status_code} from {url}: {message}")

        if not response.text.strip():
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(f"Non-JSON response from {url}: {response.text[:300]}") from exc

    raise ApiError(f"Request failed after {max_attempts} attempts: {url}")


def _backoff_delay(base_delay: float, attempt: int) -> float:
    return base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.75)


def _response_error_message(response: requests.Response) -> str:
    try:
        return json.dumps(response.json())
    except ValueError:
        return response.text[:500]


def dedupe_by(items: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], str]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = key_fn(item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def domain_to_company_name(domain: str) -> str:
    root = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
    name = root.split(".")[0].replace("-", " ").replace("_", " ").strip()
    return name.title() if name else domain


def first_name(full_name: str) -> str:
    return full_name.strip().split()[0] if full_name and full_name.strip() else "there"
