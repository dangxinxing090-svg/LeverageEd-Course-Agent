/**
 * SkipTest 跳级测试组件测试 - L6规范
 *
 * 用例:
 * 1. 渲染初始标题和开始按钮
 * 2. 点击开始调createSkipTest
 * 3. 获取题目后渲染第一题
 * 4. 完成答题后调submitSkipTest
 * 5. 通过显示"恭喜通过！"和"返回学习"
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SkipTest } from '../index';
import { createSkipTest, submitSkipTest } from '../../../services/api';

jest.mock('../../../services/api');
const mockedCreateSkipTest = createSkipTest as jest.MockedFunction<typeof createSkipTest>;
const mockedSubmitSkipTest = submitSkipTest as jest.MockedFunction<typeof submitSkipTest>;

const MOCK_USER_ID = 'user-uuid-001';
const MOCK_TOPIC_ID = 'topic-uuid-001';
const MOCK_TARGET_POINT_ID = 'point-uuid-001';

const mockTestOutput = {
  test_id: 'test-uuid-001',
  questions: [
    {
      question_id: 'q-001',
      content: 'Python中以下哪个是不可变数据类型？',
      question_type: 'single_choice',
      options: ['list', 'dict', 'tuple', 'set'],
      correct_answer: 'tuple',
    },
    {
      question_id: 'q-002',
      content: '以下哪个关键字用于定义函数？',
      question_type: 'single_choice',
      options: ['func', 'function', 'def', 'define'],
      correct_answer: 'def',
    },
  ],
  time_limit: 300,
};

const mockPassResult = {
  passed: true,
  score: 100,
  total_questions: 2,
  correct_count: 2,
  feedback: '表现优秀，已通过跳级测试！',
};

describe('SkipTest', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // 用例1: 渲染初始标题和开始按钮
  it('应渲染初始标题和开始按钮', () => {
    render(
      <SkipTest
        userId={MOCK_USER_ID}
        topicId={MOCK_TOPIC_ID}
        targetPointId={MOCK_TARGET_POINT_ID}
      />
    );

    expect(screen.getByText('跳级测试')).toBeInTheDocument();
    expect(screen.getByText('开始跳级测试')).toBeInTheDocument();
  });

  // 用例2: 点击开始调createSkipTest
  it('点击开始按钮应调用createSkipTest', async () => {
    mockedCreateSkipTest.mockResolvedValueOnce(mockTestOutput);

    render(
      <SkipTest
        userId={MOCK_USER_ID}
        topicId={MOCK_TOPIC_ID}
        targetPointId={MOCK_TARGET_POINT_ID}
      />
    );

    await userEvent.click(screen.getByText('开始跳级测试'));

    await waitFor(() => {
      expect(mockedCreateSkipTest).toHaveBeenCalledWith({
        user_id: MOCK_USER_ID,
        target_point_id: MOCK_TARGET_POINT_ID,
      });
    });
  });

  // 用例3: 获取题目后渲染第一题
  it('获取题目后应渲染第一题', async () => {
    mockedCreateSkipTest.mockResolvedValueOnce(mockTestOutput);

    render(
      <SkipTest
        userId={MOCK_USER_ID}
        topicId={MOCK_TOPIC_ID}
        targetPointId={MOCK_TARGET_POINT_ID}
      />
    );

    await userEvent.click(screen.getByText('开始跳级测试'));

    await waitFor(() => {
      expect(screen.getByText(/Python中以下哪个是不可变数据类型/)).toBeInTheDocument();
      expect(screen.getByText('tuple')).toBeInTheDocument();
      expect(screen.getByText('list')).toBeInTheDocument();
    });
  });

  // 用例4: 完成答题后调submitSkipTest
  it('完成答题后应调用submitSkipTest', async () => {
    mockedCreateSkipTest.mockResolvedValueOnce(mockTestOutput);
    mockedSubmitSkipTest.mockResolvedValueOnce(mockPassResult);

    render(
      <SkipTest
        userId={MOCK_USER_ID}
        topicId={MOCK_TOPIC_ID}
        targetPointId={MOCK_TARGET_POINT_ID}
      />
    );

    // 开始测试
    await userEvent.click(screen.getByText('开始跳级测试'));

    await waitFor(() => {
      expect(screen.getByText(/Python中以下哪个是不可变数据类型/)).toBeInTheDocument();
    });

    // 回答第一题
    await userEvent.click(screen.getByText('tuple'));
    await userEvent.click(screen.getByText('下一题'));

    await waitFor(() => {
      expect(screen.getByText(/以下哪个关键字用于定义函数/)).toBeInTheDocument();
    });

    // 回答第二题
    await userEvent.click(screen.getByText('def'));
    await userEvent.click(screen.getByText(/提交测试/));

    await waitFor(() => {
      expect(mockedSubmitSkipTest).toHaveBeenCalledWith({
        test_id: 'test-uuid-001',
        user_id: MOCK_USER_ID,
        answers: expect.any(Array),
      });
    });
  });

  // 用例5: 通过显示"恭喜通过！"和"返回学习"
  it('通过时应显示"恭喜通过！"和"返回学习"', async () => {
    mockedCreateSkipTest.mockResolvedValueOnce(mockTestOutput);
    mockedSubmitSkipTest.mockResolvedValueOnce(mockPassResult);

    render(
      <SkipTest
        userId={MOCK_USER_ID}
        topicId={MOCK_TOPIC_ID}
        targetPointId={MOCK_TARGET_POINT_ID}
      />
    );

    // 开始测试
    await userEvent.click(screen.getByText('开始跳级测试'));

    await waitFor(() => {
      expect(screen.getByText(/Python中以下哪个是不可变数据类型/)).toBeInTheDocument();
    });

    // 回答第一题
    await userEvent.click(screen.getByText('tuple'));
    await userEvent.click(screen.getByText('下一题'));

    await waitFor(() => {
      expect(screen.getByText(/以下哪个关键字用于定义函数/)).toBeInTheDocument();
    });

    // 回答第二题并提交
    await userEvent.click(screen.getByText('def'));
    await userEvent.click(screen.getByText(/提交测试/));

    await waitFor(() => {
      expect(screen.getByText('恭喜通过！')).toBeInTheDocument();
      expect(screen.getByText('返回学习')).toBeInTheDocument();
    });
  });
});
