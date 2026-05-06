import type { Plugin } from "@opencode-ai/plugin"

/**
 * validate 插件 —— Agent 写入 knowledge/articles/*.json 时自动校验格式合规性。
 *
 * 监听 tool.execute.after 事件，当 write / edit 工具写入目标目录后，
 * 调用 Python 脚本 hooks/validate_json.py 检查 JSON 的必填字段、ID 格式、
 * status 枚举、URL 格式、summary 长度、tags 数量等。
 *
 * 使用 Bun Shell API 的 $.nothrow() 执行命令，避免非零退出码导致插件崩溃。
 * 所有 shell 调用均被 try/catch 包裹，防止未捕获异常阻塞 Agent。
 */
const validatePlugin: Plugin = async (input) => {
  const { $ } = input

  return {
    async "tool.execute.after"(hookInput) {
      const { tool: toolName, args } = hookInput

      if (toolName !== "write" && toolName !== "edit") {
        return
      }

      const argsRecord = args as Record<string, unknown>
      const filePath: unknown =
        argsRecord.file_path ?? argsRecord.filePath

      if (typeof filePath !== "string") {
        return
      }

      if (
        !filePath.startsWith("knowledge/articles/") ||
        !filePath.endsWith(".json")
      ) {
        return
      }

      try {
        const result =
          await $.nothrow()`python3 hooks/validate_json.py ${filePath}`
        if (result.exitCode === 0) {
          console.log(
            `[validate] ✅ ${filePath} 格式校验通过`,
          )
        } else {
          console.error(
            `[validate] ❌ ${filePath} 格式校验失败:\n${result.text()}`,
          )
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : String(err)
        console.error(
          `[validate] ⚠️ ${filePath} 校验脚本执行异常: ${message}`,
        )
      }
    },
  }
}

export default validatePlugin
