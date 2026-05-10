/**
 * TeachingPanel 组件测试 - L6标准
 *
 * 用例:
 * 1. 渲染三个操作按钮
 * 2. 传content时不调API直接渲染
 * 3. 未传content时调getExplanation
 * 4. 成功渲染content
 * 5. 点击"练习题"触发onExercise
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TeachingPanel } from '../index';
import { getExplanation } from '../../../services/api';
import { ExplanationResponse } from '../../../types';

jest.mock('../../../services/api');
const mockedGetExplanation = getExplanation as jest.MockedFunction<typeof getExplanation>;

describe('TeachingPanel', () => {
  const mockExplanation: ExplanationResponse = {
    component_id: 'comp-1',
    content: '<h2>Python变量</h2><p>变量是存储数据的容器。</p>',
    teaching_method: '讲授法',
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('应渲染三个操作按钮', async () => {
    mockedGetExplanation.mockResolvedValueOnce(mockExplanation);

    render(<TeachingPanel componentId="comp-1" />);

    await waitFor(() => {
      expect(screen.getByText('继续讲解')).toBeInTheDocument();
      expect(screen.getByText('练习题')).toBeInTheDocument();
      expect(screen.getByText('全景页')).toBeInTheDocument();
    });
  });

  it('传content时不应调用API直接渲染', () => {
    render(
      <TeachingPanel
        componentId="comp-1"
        content="<p>直接传入的内容</p>"
      />
    );

    expect(mockedGetExplanation).not.toHaveBeenCalled();
    expect(screen.getByText('直接传入的内容')).toBeInTheDocument();
  });

  it('未传content时应调用getExplanation', async () => {
    mockedGetExplanation.mockResolvedValueOnce(mockExplanation);

    render(<TeachingPanel componentId="comp-1" />);

    await waitFor(() => {
      expect(mockedGetExplanation).toHaveBeenCalledWith('comp-1');
    });
  });

  it('成功时应渲染content', async () => {
    mockedGetExplanation.mockResolvedValueOnce(mockExplanation);

    render(<TeachingPanel componentId="comp-1" />);

    await waitFor(() => {
      expect(screen.getByText('Python变量')).toBeInTheDocument();
      expect(screen.getByText('变量是存储数据的容器。')).toBeInTheDocument();
    });
  });

  it('点击"练习题"时应触发onExercise', async () => {
    mockedGetExplanation.mockResolvedValueOnce(mockExplanation);
    const onExercise = jest.fn();

    render(<TeachingPanel componentId="comp-1" onExercise={onExercise} />);

    await waitFor(() => {
      expect(screen.getByText('Python变量')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('练习题'));
    expect(onExercise).toHaveBeenCalledTimes(1);
  });
});
