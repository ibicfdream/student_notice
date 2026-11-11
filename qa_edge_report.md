# 九组通知边缘测试报告

结果：20/20 子案例通过；0 个子案例失败。

参考日固定为北京时间 2026-11-11；跨年案例单独固定日期。全部测试不写入待办文件，也不发送提醒。

第5、7组为模拟 OCR 文本/坐标测试，不调用 PaddleOCR，不衡量图片文字识别准确率。

## 1. 分类模糊与关键词冲突

### 课程论文引用科研材料：通过

通知原文：

```text
事项：马原课程论文提交
请于11月20日18:00前上传至教学平台，可参考科研项目论文，作为本课程考核。
```

预期核对点：

```json
{
  "count": 1,
  "category": [
    "课程学业"
  ],
  "deadline": [
    "2026-11-20 18:00"
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "马原课程论文提交",
    "deadline": "2026-11-20 18:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "00前上传至教学平台",
    "category": "课程学业",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

### 竞赛论文含课程词：通过

通知原文：

```text
事项：竞赛论文提交
挑战杯竞赛论文请于11月21日18:00前通过竞赛平台提交，可附课程项目成果。
```

预期核对点：

```json
{
  "count": 1,
  "category": [
    "竞赛科研"
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "竞赛论文提交",
    "deadline": "2026-11-21 18:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "竞赛平台",
    "category": "竞赛科研",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

### 文体活动在招聘大厅：通过

通知原文：

```text
金秋相约
新生风采大赛定于11月22日19:00举行。
东区公主楼三楼招聘大厅
```

预期核对点：

```json
{
  "count": 1,
  "category": [
    "活动实践"
  ],
  "task": [
    "新生风采大赛"
  ],
  "location": [
    "东区公主楼三楼招聘大厅"
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "新生风采大赛",
    "deadline": "2026-11-22 19:00",
    "end_time": null,
    "location": "东区公主楼三楼招聘大厅",
    "submit_method": "现场参加",
    "category": "活动实践",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

### 实习证明与行政关键词：通过

通知原文：

```text
事项：提交实习证明
11月23日17:00前将盖章后的实习证明上传就业系统。
```

预期核对点：

```json
{
  "count": 1,
  "category": [
    "就业实习"
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "提交实习证明",
    "deadline": "2026-11-23 17:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "00前将盖章后的实习证明上传就业系统",
    "category": "就业实习",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

## 2. 时间缺失、模糊与非法日期

### 时间另行通知：通过

通知原文：

```text
事项：校园卡补办
请携带身份证到学生服务中心101室补办校园卡，办理时间另行通知。
```

预期核对点：

```json
{
  "count": 1,
  "deadline": [
    "未提及"
  ],
  "no_reminders": true
}
```

实际提取摘要：

```json
[
  {
    "task": "校园卡补办",
    "deadline": "未提及",
    "end_time": null,
    "location": "学生服务中心101室",
    "submit_method": "未提及",
    "category": "生活服务",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

### 预计日期不是硬截止：通过

通知原文：

```text
事项：关注奖学金评审结果
结果预计11月20日前后公布，具体以学院通知为准。
```

预期核对点：

```json
{
  "count": 1,
  "deadline": [
    "未提及"
  ],
  "no_reminders": true
}
```

实际提取摘要：

```json
[
  {
    "task": "关注奖学金评审结果",
    "deadline": "未提及",
    "end_time": null,
    "location": "未提及",
    "submit_method": "未提及",
    "category": "行政事务",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

### 非法日期不能生成提醒：通过

通知原文：

```text
事项：材料提交
请于2026年2月30日17:00前提交至教务系统。
```

预期核对点：

```json
{
  "count": 1,
  "deadline": [
    "未提及"
  ],
  "no_reminders": true
}
```

实际提取摘要：

```json
[
  {
    "task": "材料提交",
    "deadline": "未提及",
    "end_time": null,
    "location": "未提及",
    "submit_method": "00前提交至教务系统",
    "category": "其它类别",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

## 3. 多地点及地点归属

### 申请与领卡地点不同：通过

通知原文：

```text
事项：校园卡补办
11月18日12:00前到学生服务中心101室提交申请，11月20日16:00前到图书馆102室领取新卡。
```

预期核对点：

```json
{
  "count": 2,
  "deadline": [
    "2026-11-18 12:00",
    "2026-11-20 16:00"
  ],
  "location_contains": [
    "学生服务中心101",
    "图书馆102"
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "校园卡补办—提交申请",
    "deadline": "2026-11-18 12:00",
    "end_time": null,
    "location": "学生服务中心101室",
    "submit_method": "现场提交申请",
    "category": "生活服务",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  },
  {
    "task": "校园卡补办—领取新卡",
    "deadline": "2026-11-20 16:00",
    "end_time": null,
    "location": "图书馆102室",
    "submit_method": "现场领取",
    "category": "生活服务",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

### 提交地点不能被咨询地点替换：通过

通知原文：

```text
事项：奖学金材料提交
11月18日12:00前将纸质材料交至行政楼205办公室。咨询地点：图书馆报告厅（不接收材料）。
```

预期核对点：

```json
{
  "count": 1,
  "location": [
    "行政楼205办公室"
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "奖学金材料提交",
    "deadline": "2026-11-18 12:00",
    "end_time": null,
    "location": "行政楼205办公室",
    "submit_method": "纸质",
    "category": "行政事务",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

## 4. 多事项及时间、渠道和条件绑定

### 核对、纠错、提交各有时间：通过

通知原文：

```text
事项：学生信息办理
一、信息核对：11月16日-11月18日登录学生系统核对信息，有误者于11月19日17:00前到行政楼108室现场修改。
二、材料提交：11月20日18:00前上传材料至学生系统，纸质版交至学院学工办。
```

预期核对点：

```json
{
  "count": 4,
  "deadline": [
    "2026-11-16",
    "2026-11-19 17:00",
    "2026-11-20 18:00",
    "2026-11-20 18:00"
  ],
  "first_end": "2026-11-18",
  "condition_index": 1,
  "condition": "个人信息有误",
  "first_no_condition": true
}
```

实际提取摘要：

```json
[
  {
    "task": "信息核对—核对个人信息",
    "deadline": "2026-11-16",
    "end_time": "2026-11-18",
    "location": "未提及",
    "submit_method": "学生系统",
    "category": "其它类别",
    "reference_date": null,
    "time_expression": null,
    "requirements": "11月16日-11月18日登录学生系统核对信息"
  },
  {
    "task": "信息核对—现场修改信息",
    "deadline": "2026-11-19 17:00",
    "end_time": null,
    "location": "行政楼108室",
    "submit_method": "现场修改",
    "category": "其它类别",
    "reference_date": null,
    "time_expression": null,
    "requirements": "有误者于11月19日17:00前到行政楼108室现场修改"
  },
  {
    "task": "材料提交—上传材料",
    "deadline": "2026-11-20 18:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "学生系统",
    "category": "其它类别",
    "reference_date": null,
    "time_expression": null,
    "requirements": "11月20日18:00前上传材料至学生系统"
  },
  {
    "task": "材料提交—提交纸质材料",
    "deadline": "2026-11-20 18:00",
    "end_time": null,
    "location": "学院学工办",
    "submit_method": "纸质提交",
    "category": "其它类别",
    "reference_date": null,
    "time_expression": null,
    "requirements": "纸质版交至学院学工办"
  }
]
```

### 同一报名窗口不能拆成两件事：通过

通知原文：

```text
事项：课程报名
课程报名于11月16日09:00开始，11月20日18:00截止，请通过选课系统报名。
```

预期核对点：

```json
{
  "count": 1,
  "start_time": [
    "2026-11-16 09:00"
  ],
  "deadline": [
    "2026-11-20 18:00"
  ],
  "reminder_times": [
    [
      "2026-11-15 09:00",
      "2026-11-16 09:00",
      "2026-11-20 16:00"
    ]
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "课程报名",
    "deadline": "2026-11-20 18:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "选课系统",
    "category": "课程学业",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

## 5. 模拟 OCR 断行恢复

### 动作词在行尾被截断：通过

通知原文：

```text
事项：课程论文提交
请于11月19日18:00前上传到教学平台。
```

预期核对点：

```json
{
  "count": 1,
  "category": [
    "课程学业"
  ],
  "deadline": [
    "2026-11-19 18:00"
  ],
  "equivalent_plain": true
}
```

实际提取摘要：

```json
[
  {
    "task": "课程论文提交",
    "deadline": "2026-11-19 18:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "教学平台",
    "category": "课程学业",
    "reference_date": null,
    "time_expression": null,
    "requirements": null
  }
]
```

### 编号阶段内月份和系统名断行：通过

通知原文：

```text
学生信息办理
一、信息核对：请于11月16日-11月18日登录学生系统核对信息，有误者于11
月19日
17:00前到行政楼108室现场修改。
二、材料提交：11月20日18:00前上传至学
生系统，
纸质版交至学院学工办。
```

预期核对点：

```json
{
  "count": 4,
  "deadline": [
    "2026-11-16",
    "2026-11-19 17:00",
    "2026-11-20 18:00",
    "2026-11-20 18:00"
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "信息核对—核对个人信息",
    "deadline": "2026-11-16",
    "end_time": "2026-11-18",
    "location": "未提及",
    "submit_method": "学生系统",
    "category": "其它类别",
    "reference_date": null,
    "time_expression": null,
    "requirements": "请于11月16日-11月18日登录学生系统核对信息"
  },
  {
    "task": "信息核对—现场修改信息",
    "deadline": "2026-11-19 17:00",
    "end_time": null,
    "location": "行政楼108室",
    "submit_method": "现场修改",
    "category": "其它类别",
    "reference_date": null,
    "time_expression": null,
    "requirements": "有误者于11月19日17:00前到行政楼108室现场修改"
  },
  {
    "task": "材料提交—上传材料",
    "deadline": "2026-11-20 18:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "学生系统",
    "category": "其它类别",
    "reference_date": null,
    "time_expression": null,
    "requirements": "11月20日18:00前上传至学生系统"
  },
  {
    "task": "材料提交—提交纸质材料",
    "deadline": "2026-11-20 18:00",
    "end_time": null,
    "location": "学院学工办",
    "submit_method": "纸质提交",
    "category": "其它类别",
    "reference_date": null,
    "time_expression": null,
    "requirements": "纸质版交至学院学工办"
  }
]
```

## 6. 当前日期换算及原文留存

### 下周一：通过

通知原文：

```text
下周一下午两点有个实习分享会，想参加的群里接龙。
```

预期核对点：

```json
{
  "count": 1,
  "deadline": [
    "2026-11-16 14:00"
  ],
  "reference_date": [
    "2026-11-11"
  ],
  "original_relative": "下周一"
}
```

实际提取摘要：

```json
[
  {
    "task": "参加实习分享会",
    "deadline": "2026-11-16 14:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "群接龙",
    "category": "就业实习",
    "reference_date": "2026-11-11",
    "time_expression": "下周一下午2点",
    "requirements": "下周一下午两点有个实习分享会，想参加的群里接龙"
  }
]
```

### 后天没有具体时刻：通过

通知原文：

```text
后天参加班会，地点：教学楼201室。
```

预期核对点：

```json
{
  "count": 1,
  "deadline": [
    "2026-11-13"
  ],
  "reference_date": [
    "2026-11-11"
  ],
  "original_relative": "后天",
  "date_only_reminders": true
}
```

实际提取摘要：

```json
[
  {
    "task": "班会",
    "deadline": "2026-11-13",
    "end_time": null,
    "location": "教学楼201室",
    "submit_method": "现场参加",
    "category": "其它类别",
    "reference_date": "2026-11-11",
    "time_expression": "后天",
    "requirements": "后天参加班会，地点:教学楼201室"
  }
]
```

### 年末跨年：通过

通知原文：

```text
后天下午3点参加班会。
```

预期核对点：

```json
{
  "count": 1,
  "deadline": [
    "2027-01-02 15:00"
  ],
  "reference_date": [
    "2026-12-31"
  ],
  "original_relative": "后天"
}
```

实际提取摘要：

```json
[
  {
    "task": "班会",
    "deadline": "2027-01-02 15:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "未提及",
    "category": "其它类别",
    "reference_date": "2026-12-31",
    "time_expression": "后天下午3点",
    "requirements": "后天下午3点参加班会"
  }
]
```

### 指定参考日覆盖当前日：通过

通知原文：

```text
后天下午3点参加班会。
```

预期核对点：

```json
{
  "count": 1,
  "deadline": [
    "2026-11-03 15:00"
  ],
  "reference_date": [
    "2026-11-01"
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "班会",
    "deadline": "2026-11-03 15:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "未提及",
    "category": "其它类别",
    "reference_date": "2026-11-01",
    "time_expression": "后天下午3点",
    "requirements": "后天下午3点参加班会"
  }
]
```

## 7. 模拟课程表坐标与缺失单元格

### 乱序文字框及第二行缺教师：通过

通知原文：

```text
时间｜地点｜主题｜学时｜主讲教师
11月20日09:00—11:00｜三教310｜Python程序设计｜2学时｜张老师
11月21日14:00—16:00｜理科楼208｜高等数学｜2学时｜未提供
```

预期核对点：

```json
{
  "count": 2,
  "task": [
    "Python程序设计",
    "高等数学"
  ],
  "deadline": [
    "2026-11-20 09:00",
    "2026-11-21 14:00"
  ],
  "end_time": [
    "2026-11-20 11:00",
    "2026-11-21 16:00"
  ],
  "location": [
    "三教310",
    "理科楼208"
  ],
  "teacher": [
    "张老师",
    ""
  ],
  "category": [
    "课程学业",
    "课程学业"
  ],
  "warning_index": 1
}
```

送入提取器的模拟 OCR 文本：

```text
时间	地点	主题	学时	主讲教师
11月20日9:00-11:00	三教310	Python程序设计	2学时	张老师
11月21日14:00-16:00	理科楼208	高等数学	2学时	
```

实际提取摘要：

```json
[
  {
    "task": "Python程序设计",
    "deadline": "2026-11-20 09:00",
    "end_time": "2026-11-20 11:00",
    "location": "三教310",
    "submit_method": "现场上课",
    "category": "课程学业",
    "reference_date": "2026-11-11",
    "time_expression": "11月20日9:00-11:00",
    "requirements": "时间：11月20日9:00-11:00；地点：三教310；主题：Python程序设计；学时：2学时；主讲教师：张老师"
  },
  {
    "task": "高等数学",
    "deadline": "2026-11-21 14:00",
    "end_time": "2026-11-21 16:00",
    "location": "理科楼208",
    "submit_method": "现场上课",
    "category": "课程学业",
    "reference_date": "2026-11-11",
    "time_expression": "11月21日14:00-16:00",
    "requirements": "时间：11月21日14:00-16:00；地点：理科楼208；主题：高等数学；学时：2学时"
  }
]
```

## 8. 群消息与口语化条件

### 材料照片、纸质版及自愿分享会：通过

通知原文：

```text
@所有人 明天（周四）中午12点前把实习证明拍照发我微信。还没交的这周五之前交纸质版到经管楼507。另外下周三下午两点有个实习分享会，想参加的群里接龙。
```

预期核对点：

```json
{
  "count": 3,
  "deadline": [
    "2026-11-12 12:00",
    "2026-11-12",
    "2026-11-18 14:00"
  ],
  "method_contains": [
    "微信",
    "纸质",
    "群接龙"
  ],
  "optional_index": 2,
  "no_mention_in_tasks": true
}
```

实际提取摘要：

```json
[
  {
    "task": "提交实习证明照片",
    "deadline": "2026-11-12 12:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "微信发送照片（发给通知发布者）",
    "category": "就业实习",
    "reference_date": "2026-11-11",
    "time_expression": "明天(周四)中午12点前",
    "requirements": "@所有人 明天(周四)中午12点前把实习证明拍照发我微信"
  },
  {
    "task": "提交实习证明纸质版",
    "deadline": "2026-11-12",
    "end_time": null,
    "location": "经管楼507",
    "submit_method": "纸质提交",
    "category": "就业实习",
    "reference_date": "2026-11-11",
    "time_expression": "这周五之前",
    "requirements": "还没交的这周五之前交纸质版到经管楼507"
  },
  {
    "task": "参加实习分享会",
    "deadline": "2026-11-18 14:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "群接龙",
    "category": "就业实习",
    "reference_date": "2026-11-11",
    "time_expression": "下周三下午2点",
    "requirements": "另外下周三下午两点有个实习分享会，想参加的群里接龙"
  }
]
```

## 9. 复杂比赛报名聚合

### 赛题和组织介绍不是任务：通过

通知原文：

```text
关于第六届大学生智能制造创新大赛的通知
一、赛事背景
培养实践能力，赛题包括机器人足球和论文研究。
二、赛题介绍
共设置10个题目，每题另附评分说明；颁奖典礼定于12月1日举行。
三、组委会工作
组织教学研讨、招聘交流。
四、选手须知
每支参赛队伍学生人数3-5名，每名学生仅可参加1支队伍。本次报名与资料上传统一通过官网https://contest.example.com线上报送。参赛队伍须于2026年11月25日17:00前完成系统报名，同时将报名材料打包发送至team@example.como。报名材料命名为“学校-姓名-赛题”，报名信息提交后不得变更队伍成员。
```

预期核对点：

```json
{
  "count": 1,
  "deadline": [
    "2026-11-25 17:00"
  ],
  "category": [
    "竞赛科研"
  ],
  "method_contains_all": [
    "https://contest.example.com",
    "team@example.com"
  ],
  "method_excludes": [
    "example.como"
  ],
  "requirements_contains": [
    "3-5名",
    "命名",
    "不得变更"
  ],
  "task_contains": [
    "智能制造创新大赛报名"
  ]
}
```

实际提取摘要：

```json
[
  {
    "task": "第六届大学生智能制造创新大赛报名",
    "deadline": "2026-11-25 17:00",
    "end_time": null,
    "location": "未提及",
    "submit_method": "系统报名：https://contest.example.com线上报送；报名材料发送至邮箱：team@example.com",
    "category": "竞赛科研",
    "reference_date": null,
    "time_expression": null,
    "requirements": "四、选手须知每支参赛队伍学生人数3-5名；每名学生仅可参加1支队伍；报名材料需打包；报名材料命名为“学校-姓名-赛题”；报名信息提交后不得变更队伍成员"
  }
]
```
