/**
 * 学习进度存储工具
 * 使用 localStorage 记录每个知识组件的学习状态和练习状态
 * 同时同步到后端数据库
 */

import { updateComponentStatus } from '../api/behavior';

const STORAGE_PREFIX = 'learn_progress_';

export type LearnStatus = 'none' | 'learning' | 'completed';
export type ExerciseStatus = 'none' | 'practicing' | 'passed';

export interface ComponentProgress {
  learnStatus: LearnStatus;
  exerciseStatus: ExerciseStatus;
}

/**
 * 获取单个知识组件的进度
 */
export function getComponentProgress(componentId: string): ComponentProgress {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + componentId);
    if (raw) {
      return JSON.parse(raw) as ComponentProgress;
    }
  } catch (e) {
    // ignore
  }
  return { learnStatus: 'none', exerciseStatus: 'none' };
}

/**
 * 设置单个知识组件的进度
 */
export function setComponentProgress(componentId: string, progress: Partial<ComponentProgress>): ComponentProgress {
  const current = getComponentProgress(componentId);
  const updated = { ...current, ...progress };
  localStorage.setItem(STORAGE_PREFIX + componentId, JSON.stringify(updated));
  return updated;
}

/**
 * 记录知识组件为"学习中"
 */
export function markLearning(componentId: string): ComponentProgress {
  const result = setComponentProgress(componentId, { learnStatus: 'learning' });
  const topicId = localStorage.getItem('currentTopicId') || undefined;
  updateComponentStatus(componentId, 'in_progress', topicId).catch(() => {});
  return result;
}

/**
 * 记录知识组件讲解"完成学习"
 */
export function markLearnCompleted(componentId: string): ComponentProgress {
  const result = setComponentProgress(componentId, { learnStatus: 'completed' });
  const topicId = localStorage.getItem('currentTopicId') || undefined;
  updateComponentStatus(componentId, 'learn_completed', topicId).catch(() => {});
  return result;
}

/**
 * 记录知识组件"做题中"
 */
export function markPracticing(componentId: string): ComponentProgress {
  const result = setComponentProgress(componentId, { exerciseStatus: 'practicing' });
  const topicId = localStorage.getItem('currentTopicId') || undefined;
  updateComponentStatus(componentId, 'practicing', topicId).catch(() => {});
  return result;
}

/**
 * 记录知识组件"练习通过"
 */
export function markExercisePassed(componentId: string): ComponentProgress {
  const result = setComponentProgress(componentId, { exerciseStatus: 'passed' });
  const topicId = localStorage.getItem('currentTopicId') || undefined;
  updateComponentStatus(componentId, 'exercise_passed', topicId).catch(() => {});
  return result;
}

/**
 * 获取所有知识组件的进度
 */
export function getAllProgress(): Record<string, ComponentProgress> {
  const result: Record<string, ComponentProgress> = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(STORAGE_PREFIX)) {
        const componentId = key.slice(STORAGE_PREFIX.length);
        result[componentId] = getComponentProgress(componentId);
      }
    }
  } catch (e) {
    // ignore
  }
  return result;
}
