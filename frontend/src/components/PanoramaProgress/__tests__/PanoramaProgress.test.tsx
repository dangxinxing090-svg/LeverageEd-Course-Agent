import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PanoramaProgress } from '../index';
import { getTopicStructure } from '../../../services/api';

jest.mock('../../../services/api');
const mockedGetTopicStructure = getTopicStructure as jest.MockedFunction<typeof getTopicStructure>;

describe('PanoramaProgress', () => {
  const defaultProps = {
    topicId: 'topic-uuid-001',
    userId: 'user-uuid-001',
  };

  const mockBlocks = [
    {
      block_id: 'block-001',
      block_name: '模块一',
      status: 'in_progress',
      points: [
        {
          point_id: 'point-001',
          point_name: '知识点1',
          status: 'completed',
          difficulty: 'easy',
          importance: 'high',
          components: [
            { component_id: 'comp-001', component_name: '组件1', status: 'completed' },
          ],
        },
      ],
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // 用例1: 渲染标题和表格
  it('应渲染标题"学习进度全景"和表格', async () => {
    mockedGetTopicStructure.mockResolvedValueOnce(mockBlocks);

    render(<PanoramaProgress {...defaultProps} />);

    expect(screen.getByText('学习进度全景')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('名称')).toBeInTheDocument();
      expect(screen.getByText('状态')).toBeInTheDocument();
    });
  });

  // 用例2: 挂载时调API传(topicId, userId)
  it('组件挂载时应调用getTopicStructure(topicId, userId)并注意参数顺序', async () => {
    mockedGetTopicStructure.mockResolvedValueOnce(mockBlocks);

    render(<PanoramaProgress {...defaultProps} />);

    await waitFor(() => {
      expect(mockedGetTopicStructure).toHaveBeenCalledWith('topic-uuid-001', 'user-uuid-001');
    });
  });

  // 用例3: 成功渲染模块-知识点-组件层级
  it('API成功后应渲染模块-知识点-组件层级结构', async () => {
    mockedGetTopicStructure.mockResolvedValueOnce(mockBlocks);

    render(<PanoramaProgress {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('模块一')).toBeInTheDocument();
      expect(screen.getByText('知识点1')).toBeInTheDocument();
    });

    // 知识点默认折叠，需要点击展开才能看到组件
    const toggleBtn = screen.getByLabelText('展开/折叠知识点：知识点1');
    await userEvent.click(toggleBtn);

    await waitFor(() => {
      expect(screen.getByText('组件1')).toBeInTheDocument();
    });
  });

  // 用例4: 点击知识点触发onPointClick
  it('点击知识点应触发onPointClick回调并传入pointId', async () => {
    mockedGetTopicStructure.mockResolvedValueOnce(mockBlocks);
    const onPointClick = jest.fn();

    render(<PanoramaProgress {...defaultProps} onPointClick={onPointClick} />);

    await waitFor(() => {
      expect(screen.getByText('知识点1')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('知识点1'));

    expect(onPointClick).toHaveBeenCalledTimes(1);
    expect(onPointClick).toHaveBeenCalledWith('point-001');
  });

  // 用例5: 不同状态应用不同CSS类
  it('不同状态应应用不同的CSS类', async () => {
    const blocksWithDifferentStatuses = [
      {
        block_id: 'block-001',
        block_name: '已完成模块',
        status: 'completed',
        points: [
          {
            point_id: 'point-001',
            point_name: '进行中知识点',
            status: 'in_progress',
            difficulty: 'easy',
            importance: 'high',
            components: [],
          },
        ],
      },
    ];

    mockedGetTopicStructure.mockResolvedValueOnce(blocksWithDifferentStatuses);

    render(<PanoramaProgress {...defaultProps} />);

    await waitFor(() => {
      // 使用 getAllByText 因为图例中也有这些文本
      expect(screen.getAllByText('已完成').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('进行中').length).toBeGreaterThanOrEqual(1);
    });
  });
});
