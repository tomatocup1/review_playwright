/**
 * deleteTask prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * deleteTask prompt 參數介面
 */
export interface DeleteTaskPromptParams {
    taskId: string;
    task?: Task;
    success?: boolean;
    message?: string;
    isTaskCompleted?: boolean;
}
/**
 * 獲取 deleteTask 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getDeleteTaskPrompt(params: DeleteTaskPromptParams): string;
