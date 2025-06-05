/**
 * verifyTask prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * verifyTask prompt 參數介面
 */
export interface VerifyTaskPromptParams {
    task: Task;
    score: number;
    summary: string;
}
/**
 * 獲取 verifyTask 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getVerifyTaskPrompt(params: VerifyTaskPromptParams): string;
