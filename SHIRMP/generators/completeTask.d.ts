/**
 * completeTask prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * completeTask prompt 參數介面
 */
export interface CompleteTaskPromptParams {
    task: Task;
    completionTime: string;
}
/**
 * 獲取 completeTask 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getCompleteTaskPrompt(params: CompleteTaskPromptParams): string;
