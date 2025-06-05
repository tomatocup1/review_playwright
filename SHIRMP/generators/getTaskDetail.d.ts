/**
 * getTaskDetail prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * getTaskDetail prompt 參數介面
 */
export interface GetTaskDetailPromptParams {
    taskId: string;
    task?: Task | null;
    error?: string;
}
/**
 * 獲取 getTaskDetail 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getGetTaskDetailPrompt(params: GetTaskDetailPromptParams): string;
