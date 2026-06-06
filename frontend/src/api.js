// 与后端交互的薄封装。

const SAMPLE = `旧城轨迹

第一章 归来

　　火车进站时，雨正下得密。沈墨提着一只旧皮箱站在月台上，看着头顶斑驳的站牌。七年了，这座小城的站台还是老样子。
　　他没想到自己真的会回来。当年走得那么决绝，可此刻站在熟悉的雨里，心口还是不争气地发紧。
　　"沈墨？"一个女声从身后传来。他回过头，看见林晚撑着一把藏青色的伞。
　　"是我。"沈墨努力让声音听起来平静，"好久不见。"
　　"七年。"林晚淡淡地说，"你父亲的事，我听说了。节哀。"

第二章 旧宅

　　第二天清晨，沈墨独自回到老宅。院子里那棵石榴树枯了大半。
　　他忽然想起小时候，父亲就坐在那把藤椅上给他讲旧事。那时候他总觉得啰嗦，现在却宁愿再听一万遍。
　　桌上压着一封没寄出的信，信封上是父亲的字迹。他拆开，里面只有一行：城东的老钟楼下，我替你留了样东西。

第三章 钟楼

　　黄昏，城东的老钟楼。夕阳把影子拉得很长。
　　沈墨在石缝里摸索许久，掏出一个锈迹斑斑的铁皮盒子，里面是一沓泛黄的照片和一块旧怀表。
　　"原来你一直都记得。"沈墨的声音哽住了。他终于明白，有些爱从来不说出口，却一直藏在最深的地方。
　　林晚走过来，轻声说："找到了？"
　　"嗯。"沈墨把怀表攥在掌心，"我想，我大概不会再走了。"`

export function sampleNovel() {
  return SAMPLE
}

async function post(url, body) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || '请求失败')
  }
  return resp.json()
}

export function convert(payload) {
  return post('/api/convert', payload)
}

export function exportYaml(screenplay) {
  return post('/api/export', { screenplay })
}

export async function health() {
  const resp = await fetch('/api/health')
  return resp.json()
}
