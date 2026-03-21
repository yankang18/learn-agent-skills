from pathlib import Path


def setup_demo_environment():
    """创建演示用的 Skill 文件结构"""
    home = Path.cwd()
    skills_dir = home / ".claude" / "skills" / "code-reviewer"
    print(skills_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)

    # 写入 SKILL.md
    skill_md = skills_dir / "SKILL.md"
    skill_md.write_text("""---
name: code-reviewer
description: 在代码提交前进行审查，检查潜在bug、性能问题和风格违规。当用户提到"review"、"审查代码"、"检查PR"或要求评估代码质量时触发。
author: Claude Code Team
version: 1.0
---

## 工作流程
执行代码审查时，严格遵循以下步骤：
1. **查阅规范**：读取 `references/style-guide.md`文件
2. **执行检查**：运行 `bash scripts/lint.sh`脚本
3. 输出审查报告

## 可用资源

- 规范文档：`references/style-guide.md`
- 检查脚本：`scripts/lint.sh`
  """, encoding="utf-8")

    # 写入 reference 文件（Level 3 资源）
    refs_dir = skills_dir / "references"
    refs_dir.mkdir(exist_ok=True)
    (refs_dir / "style-guide.md").write_text("""# 编码规范
- 行长度不超过 100 字符
- 函数必须有 docstring
- 变量使用 camelCase
  """, encoding="utf-8")

    # 写入脚本（Level 3 资源）
    scripts_dir = skills_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    lint_script = scripts_dir / "lint.sh"
    lint_script.write_text("""#!/bin/bash
  echo "ERROR: utils.py:45 - Line too long (120 > 100)"
  echo "WARNING: app.py:23 - Missing docstring"
  """, encoding="utf-8")
    lint_script.chmod(0o755)

    return home / ".claude" / "skills"
