"""UZI-Skill 调用工具"""

import os
import subprocess
import json
from langchain_core.tools import tool


@tool
def run_uzi_analysis(ticker: str, depth: str = "medium") -> str:
    """调用UZI-Skill做完整量化分析(22维+65位评委+DCF/BCG)。需先clone UZI-Skill。depth: lite/medium/deep。"""
    uzi_path = os.environ.get("UZI_PATH", "../UZI-Skill")
    if not os.path.isdir(uzi_path):
        return (f"UZI-Skill未安装。运行: git clone https://github.com/wbh604/UZI-Skill.git {uzi_path}\n"
                f"然后: cd {uzi_path} && pip install -r requirements.txt")

    cmd = f"python run.py {ticker} --depth {depth} --no-browser"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600, cwd=uzi_path)
        if result.returncode != 0:
            return f"UZI运行失败(exit={result.returncode}): {result.stderr[-300:]}"

        # 尝试读 synthesis.json
        import glob
        cache = os.path.join(uzi_path, "skills", "deep-analysis", "scripts", ".cache")
        for root, _, files in os.walk(cache):
            for f in files:
                if "synthesis" in f and f.endswith(".json"):
                    with open(os.path.join(root, f), encoding="utf-8") as fp:
                        s = json.load(fp)
                    return f"UZI分析完成({depth}): 评分{s.get('composite_score','?')} 判定:{s.get('verdict','?')}"

        return f"UZI运行完成\n{result.stdout[-2000:]}"
    except subprocess.TimeoutExpired:
        return "UZI运行超时(>10分钟)，建议用lite模式"
    except Exception as e:
        return f"UZI异常: {str(e)}"
