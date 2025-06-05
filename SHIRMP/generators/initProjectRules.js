/**
 * initProjectRules prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { loadPrompt, loadPromptFromTemplate } from "../loader.js";
/**
 * 獲取 initProjectRules 的完整 prompt
 * @param params prompt 參數（可選）
 * @returns 生成的 prompt
 */
export function getInitProjectRulesPrompt(params) {
    const indexTemplate = loadPromptFromTemplate("initProjectRules/index.md");
    // 載入可能的自定義 prompt (通過環境變數覆蓋或追加)
    return loadPrompt(indexTemplate, "INIT_PROJECT_RULES");
}
//# sourceMappingURL=initProjectRules.js.map