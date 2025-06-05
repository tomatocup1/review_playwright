/**
 * initProjectRules prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
/**
 * initProjectRules prompt 參數介面
 */
export interface InitProjectRulesPromptParams {
}
/**
 * 獲取 initProjectRules 的完整 prompt
 * @param params prompt 參數（可選）
 * @returns 生成的 prompt
 */
export declare function getInitProjectRulesPrompt(params?: InitProjectRulesPromptParams): string;
