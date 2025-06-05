/**
 * listTasks prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * listTasks prompt 參數介面
 */
export interface ListTasksPromptParams {
    status: string;
    tasks: Record<string, Task[]>;
    allTasks: Task[];
}
/**
 * 獲取 listTasks 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getListTasksPrompt(params: ListTasksPromptParams): string;
