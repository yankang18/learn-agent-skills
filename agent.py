import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from prompts import base_system_prompt
from skills import SkillRegistry
from tools import Tool, SkillTool, BashTool, ReadFileTool
from llms import LLMClient


class AgentLoop:
    """
    Agent Loop - 模拟 Claude Code 的核心交互循环
    实现渐进披露的三级加载机制
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self.tools: Dict[str, Tool] = {}
        self.context: Dict[str, Any] = {}  # 当前激活的 Skill 上下文
        self.conversation_history: List[Dict] = []

        # 注册工具
        self._register_tool(SkillTool(registry))
        self._register_tool(BashTool())
        # ReadFile 需要在运行时动态创建（因为依赖当前 context）

        self.llm_client = LLMClient()

    def _register_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    def _build_system_prompt(self) -> str:
        """构建系统提示词（仅包含 Level 1 披露）"""
        return base_system_prompt.format(skills_registry=self.registry.get_registry_prompt())

    def _get_tool_schema(self):
        return [t.to_schema() for t in self.tools.values()]

    def _parse_model_output(self, output: str) -> Optional[Dict]:
        """解析模型的工具调用意图"""
        # 模拟模型输出：检查是否包含工具调用 JSON
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass

        # 简单的意图匹配（用于演示）
        if "Skill" in output and "code-reviewer" in output:
            return {"tool": "Skill", "params": {"command": "code-reviewer"}}
        elif "git diff" in output:
            return {"tool": "Bash", "params": {"command": "git diff", "description": "获取代码变更"}}
        elif "ReadFile" in output and "style-guide" in output:
            return {"tool": "ReadFile", "params": {"file_path": "references/style-guide.md"}}
        elif "lint.sh" in output:
            return {"tool": "Bash", "params": {"command": "bash scripts/lint.sh", "description": "运行代码检查"}}

        return None

    def _model_inference(self, messages: List[Dict]) -> dict:
        system_prompt = self._build_system_prompt()
        tool_schema = self._get_tool_schema()
        print(f"tool_schema: \n {json.dumps(tool_schema, ensure_ascii=False, indent=4)}")
        response = self.llm_client.inference(
            messages=messages,
            system_prompt=system_prompt,
            tool_schema=tool_schema)
        return response

    def run(self, user_input: str):
        """运行 Agent Loop，展示渐进披露全过程"""
        print("=" * 80)
        print(f"用户输入: {user_input}")
        print("=" * 80)

        # ---------------------------------------------
        # Level 1 披露 - 系统提示词（仅元数据）
        # ---------------------------------------------

        # Step 1: Level 1 披露 - 系统提示词（仅元数据）
        system_prompt = self._build_system_prompt()
        print("\n【Level 1 披露 - 系统提示词片段】")
        print("-" * 40)
        print(system_prompt)
        print(f"\n[Token 消耗: 约 {len(system_prompt)} 字符（仅元数据）]")

        # ---------------------------------------------
        # Level 2
        # ---------------------------------------------

        # Step 2: 模型意图判断（已经注册了 Skill 工具）
        print("\n" + "=" * 80)
        print("Step 2: 模型基于 Level 1 元数据判断意图")
        print("=" * 80)
        messages = []

        messages.append({
            "role": "user",
            "content": user_input,
        })

        reasoning = self._model_inference(messages)
        print(reasoning)

        status = reasoning["status"]
        if status == "succeed":
            content = reasoning["content"]
            messages.append({
                "role": "assistant",
                "content": content,
            })

            stop_reason = reasoning["stop_reason"]
            if stop_reason == "tool_calls":
                tools = reasoning["tools"]
                for tool in tools:
                    func_name = tool["function_name"]
                    arguments = tool["arguments"]
                    tool_call_id = tool["tool_call_id"]
                    tool_result = self.tools[func_name].execute(**arguments)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,  # 必须对应调用的 id
                        "content": str(tool_result)
                    })

                    reasoning = self._model_inference(messages)
                    print(reasoning)

            elif stop_reason == "stop":
                print(content)
            else:
                print(stop_reason)

        # # Step 3: 如果匹配到技能（Skill），使用Skill工具加载对应技能的Skills.md
        # tool_call = self._parse_model_output(reasoning)
        # if tool_call and tool_call["tool"] == "Skill":
        #     print("\n【Level 2 披露 - 加载完整 SKILL.md】")
        #     print("-" * 40)
        #
        #     skill_tool = self.tools["Skill"]
        #     result = skill_tool.execute(**tool_call["params"])
        #
        #     # 保存上下文（Base Path 是关键）
        #     self.context = {
        #         "skill_name": result["command_name"],
        #         "base_path": result["base_path"],
        #         "skill_content": result["content"]
        #     }
        #
        #     print(f"技能名称: {result['command_name']}")
        #     print(f"Base Path: {result['base_path']}")
        #     print(f"内容长度: {len(result['content'])} 字符")
        #     print("\n【SKILL.md 内容（已注入上下文）】")
        #     print(result['content'][:500] + "..." if len(result['content']) > 500 else result['content'])
        #
        #     # 现在创建 ReadFile 工具（绑定当前 Base Path）
        #     readfile_tool = ReadFileTool(self.context)
        #     self._register_tool(readfile_tool)
        #
        #     # Step 4: 执行 Skill 指令（多轮工具调用）
        #     # TODO: 通过Agent Tool 执行 Skill 的 多轮工具调用，并记录结果
        #     print("\n" + "=" * 80)
        #     print("Step 4: 按 Skill 指令执行（Level 3 按需披露）")
        #     print("=" * 80)
        #
        #     # 模拟执行 Skill 中的步骤
        #     execution_steps = [
        #         ("Bash", {"command": "git diff", "description": "获取代码变更"}),
        #         ("ReadFile", {"file_path": "references/style-guide.md"}),  # 相对路径！
        #         ("Bash", {"file_path": "scripts/lint.sh"}),  # 实际上是 Bash，这里演示路径解析
        #     ]
        #
        #     for i, (tool_name, params) in enumerate(execution_steps, 1):
        #         print(f"\n执行步骤 {i}: {tool_name}({params})")
        #
        #         if tool_name == "ReadFile":
        #             # 展示 Level 3 披露：相对路径解析
        #             full_path = Path(self.context['base_path']) / params['file_path']
        #             print(f"  相对路径 '{params['file_path']}' 解析为: {full_path}")
        #
        #         tool = self.tools.get(tool_name)
        #         if tool:
        #             result = tool.execute(**params)
        #             if result["status"] == "success":
        #                 content = result.get("content", result.get("stdout", ""))
        #                 preview = content[:200] + "..." if len(content) > 200 else content
        #                 print(f"  结果: {preview}")
        #             else:
        #                 print(f"  错误: {result.get('message', '')}")
        #
        # print("\n" + "=" * 80)
        # print("任务完成")
        # print("=" * 80)
        # print("\n【披露层级总结】")
        # print("Level 1: 始终保留 - Skills Registry (仅元数据)")
        # print("Level 2: 触发加载 - SKILL.md 完整内容（一次性）")
        # print("Level 3: 按需加载 - references/, scripts/ 等资源（执行时动态）")


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
1. 获取变更内容（`git diff`）
2. **查阅规范**：读取 `references/style-guide.md`
3. **执行检查**：运行 `bash scripts/lint.sh`
4. 输出审查报告

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


if __name__ == "__main__":
    # 设置演示环境
    print("初始化 Skill 环境...")
    skills_dir = setup_demo_environment()

    # 创建 Agent
    registry = SkillRegistry(skills_dir)
    agent = AgentLoop(registry)

    # 运行示例：用户请求代码审查
    agent.run("帮我审查一下刚才提交的代码")
    #
    # print("\n" + "=" * 80)
    # print("对比：如果没有渐进披露，系统提示词需要包含所有 Skill 的完整内容")
    # print(f"当前 Skills 数量: {len(registry._skills)}")
    # print(f"Level 1 披露大小: ~{len(registry.get_registry_prompt())} 字符")
    #
    # total_content = sum(len(s.content) for s in registry._skills.values())
    # print(f"若全量加载需: ~{total_content} 字符")
    # print(f"节省比例: {(1 - len(registry.get_registry_prompt()) / total_content) * 100:.1f}%")
