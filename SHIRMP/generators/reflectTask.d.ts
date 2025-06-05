/**
 * reflectTask prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
/**
 * reflectTask prompt 參數介面
 */
export interface ReflectTaskPromptParams {
    summary: string;
    analysis: string;
}
/**
 * 獲取 reflectTask 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getReflectTaskPrompt(params: ReflectTaskPromptParams): string;
