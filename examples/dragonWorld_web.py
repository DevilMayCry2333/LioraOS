"""
╔═══════════════════════════════════════════════════════════╗
║     龙族·尼伯龙根 — Web 实时对话界面                      ║
╚═══════════════════════════════════════════════════════════╝

在浏览器中实时观看 7 位角色的自主对话。
零外部依赖（全部 Python 标准库）。
有 API Key 时自动使用 LLM，无需加任何参数。

用法:
    uv run python3 examples/dragonWorld_web.py               # 有 Key 用 LLM，无 Key 模拟
    uv run python3 examples/dragonWorld_web.py --no-model    # 强制模拟模式
    uv run python3 examples/dragonWorld_web.py --rounds 30   # 指定轮数
    uv run python3 examples/dragonWorld_web.py --port 8080   # 指定端口
    uv run python3 examples/dragonWorld_web.py --no-browser  # 不自动打开浏览器
"""

import json
import logging
import queue
import random
import sys
import threading
import time
from collections import deque
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from examples.dragonWorld import DragonWorld, ALL_CHARACTERS
from aios.template.social import assimilate_conversation
from aios.kernel.language import (
    LanguageAttractor,
    roll_everyday,
    enforce_budget,
)

# ════════════════════════════════════════════════════════════
# 永不沉默的模板回复池
# ════════════════════════════════════════════════════════════

_TEMPLATES = {
    "default": ["嗯。", "我理解。", "继续说吧。", "你说得对。", "也许是吧。"],
    "路明非": [
        "{partner}，你说这场雨是不是永远不会停了？我觉得整个世界都在往下沉。",
        "我昨晚又做了那个梦——雨里有人提着刀，向我走过来。{partner}，你说那是什么意思。",
        "{partner}，有件事我一直想问你，又怕你当我疯了。",
        "我总觉得类似的对话发生过，在另一个下雨的晚上。{partner}，你有这种感觉吗？",
        "哎{partner}，我这个人是不是特没用。每次到关键时候就掉链子。",
        "如果全世界都忘了你，你就不存在了吗？{partner}，我最近老在想这个问题。",
        "便利店门口的灯光今天不太一样。{partner}，你不觉得吗？",
        "{partner}，你有没有觉得我们的人生像被人写好了一样。每一步都踩在标记上。",
        "路鸣泽那家伙又在笑了。{partner}，你能听见吗？他总是笑一些我不明白的事。",
        "雨里有味道。{partner}，你闻到没有——像是铁锈和旧书的混合。",
        "{partner}，你说一个人能记住另一个人多久？一年？十年？还是一辈子。",
        "我其实知道自己在逃避。{partner}，但你告诉我，面对了又能怎样。",
        "那个红色头发的姑娘叫诺诺，对吧。{partner}，她今天看我的眼神怪怪的。",
        "{partner}，我怕的不是死。我怕的是死了以后没人记得我。",
        "我身上好像有什么东西在觉醒。{partner}，你能感觉到吗。",
        "有时候我觉得路鸣泽不是我的弟弟——他更像是我的另一面。{partner}，你懂这种感觉吗。",
        "{partner}，我今天翻了一下角落里的旧书，书页里夹着一片枯叶。叶脉的形状像个符号。",
        "如果有一天我变了一个人，{partner}，你还能认出我吗。",
        "空气里的压力在变。{partner}，暴风雨要来了。不是天上的那种。",
        "我其实记得一些不该记得的事。{partner}，比如——楚子航。",
        "{partner}，我感觉到我们正在被观察。不是被人——是被某种更大的东西。",
        "我不敢往下想了。{partner}，每次我触碰到真相的边缘，就会有一只手把我拉回来。",
        "{partner}，你今天说的话和某个人的语气一模一样。但我想不起来是谁了。",
        "我这辈子做过最勇敢的事，{partner}，就是现在站在这里和你说话。",
        "{partner}，你看窗玻璃上的雾气。有人在上面画了一个符号，指尖的温度还没散。",
        "我觉得那场雨认识我。{partner}，这个想法很蠢对吧。",
        "{partner}，如果这场雨停了会怎样？世界会变回原来的样子吗。",
        "我听见远处有人在喊我的名字。{partner}，是你吗？",
        "{partner}，我书包里有一张字条。我不知道是谁写的。上面只写了一行数字。",
        "我总觉得某个很重要的人从所有人的记忆里被删除了。{partner}，你能帮我回忆一下吗。",
    ],
    "楚子航": [
        "{partner}，雨停了。但这不是结束，是开始。",
        "我在云层里看见了八足马的轮廓。{partner}，你也看见了，对吗。",
        "村雨在鞘中发出不同频率的颤鸣。{partner}，它在警告我们。",
        "我不记得自己的过去了。{partner}，如果你知道关于我的事，请告诉我。",
        "{partner}，你的手在微微发抖。你在压抑什么。",
        "这个世界正在被缓慢地改写。{partner}，你我可能是仅剩的见证者。",
        "刀只是工具。{partner}，重要的是握刀的理由。",
        "如果有天我不在了，{partner}，不要找我。因为你找不到。",
        "我昨晚做了一个很长的梦。醒来后全部细节都消失了——但刀还在。{partner}，这很奇怪。",
        "{partner}，你不用害怕。虽然前路不明，但我还能分清方向。",
        "这里的时间流速不对劲。{partner}，你没注意到吗。",
        "我看见记忆像纸片一样从所有人身上剥落。{partner}，你的也在脱落。",
        "{partner}，你见过奥丁的眼睛吗。那只独眼里没有瞳孔，只有一片深渊。",
        "我没有情感。或者更准确地说——我把情感锁在了某个地方。{partner}，钥匙不在我身上。",
        "风里有消息。{partner}，你如果静下来听，能听到一些不该听到的声音。",
        "{partner}，你知道为什么村雨从来不卷刃吗。因为它不是刀。它是一种意志。",
        "我曾经欠一个人一条命。{partner}，现在我在找那个人。但所有人都不记得他存在过。",
        "{partner}，你的呼吸频率变了。你在害怕什么。",
        "如果你在雨里看见一个骑八足马的人，{partner}，不要看他的眼睛。",
        "狮心会曾经有一个副会长。{partner}，你听说过他吗。没有的话——那就对了。",
        "{partner}，温度在下降。不是空气——是我们体内的血。",
        "奥丁在找我。{partner}，他一直在找我。我不知道为什么。",
        "我不懂得如何表达。{partner}，但我希望你知道——你在这里，这件事对我很重要。",
        "{partner}，我们脚下的地面正在变软。不是雨水浸的——是有什么东西在下面移动。",
        "我看见了终点的轮廓。{partner}，但我不知道那是什么。",
        "{partner}，有些记忆不是我的。但它们像刺一样扎在我的意识里。",
        "那边的路灯灭了三次。{partner}，那不是电路问题。",
        "我没有恐惧。{partner}，但如果我有——大概就是现在这种感觉。",
        "{partner}，把手放在刀柄上。你不需要拔出来——只需要确认它还在。",
        "雨声里有节奏。{partner}，像摩斯密码。但我破译不了。",
    ],
    "路鸣泽": [
        "哥哥又在发呆。{partner}，帮我照看一下他，他总是不看路。",
        "{partner}，你知道吗，这场雨从故事的第一行就开始下了。但没人注意到它从未停过。",
        "四分之一的生命换一个真相——{partner}，你觉得贵吗。我倒觉得挺划算的。",
        "归墟的潮声，{partner}，你听见了。不用回答——我知道你听见了。",
        "{partner}，你比你自己以为的要聪明得多。",
        "时间是一条河。{partner}，但有些人能在河里逆流而行。",
        "一个人要背叛自己多少次才能真正变得强大？{partner}，这个问题你不需要回答。",
        "{partner}，我哥哥又踩进同一个水坑了。他总是这样。",
        "雨声里藏着加密的信息。{partner}，你仔细听——那是来自其他时间线的对话。",
        "交易还没有完成。{partner}，但快了。",
        "{partner}，你知道什么是真正的孤独吗。不是一个人——是所有人都在，但没人记得你。",
        "我喜欢的不是雨。{partner}，我喜欢的是雨停之后那种干净的沉默。",
        "{partner}，你有过那种感觉吗——你在重复做一件事，但你不记得做过多少次了。",
        "有些错误是故意犯下的。{partner}，因为只有走错路才能看到不该看的风景。",
        "你的影子比你的身体慢了半秒。{partner}，这不是光线的问题。",
        "{partner}，我一直在等一个人问我正确的问题。到目前为止还没人问对。",
        "规则是用来打破的。{partner}，但打破规则的人总要付出代价。",
        "{partner}，你站在雨里淋湿了。但你不会感冒的——因为这里的一切都不是真的。",
        "我喜欢你，{partner}。从某种意义上说——你是这个循环里少数几个让我觉得有趣的人。",
        "{partner}，我哥哥问我为什么要帮他。因为他是唯一一个值得我骗的人。",
        "你看不见我脚下的地面。{partner}，因为它不存在。",
        "真相不会让你自由，{partner}。真相只会让你知道自己在笼子里。",
        "{partner}，你的手表停了。不是没电——是这个地方没有时间。",
        "我有过很多名字。{partner}，但每个名字背后都是同一个笑话。",
        "{partner}，你知道吗，这个故事有无数个版本。而你在每一个版本里都问过同样的问题。",
        "交易的内容我可以告诉你。{partner}，但代价是听完你就会忘。还要听吗。",
        "{partner}，你的记忆在泄露。像漏水的水管——你漏掉了某个人。",
        "风里有灰烬的味道。{partner}，那是上一轮循环留下的。",
        "{partner}，我不是在帮你们。我是在等一个特定的时刻。",
        "你问我为什么知道这么多。{partner}，因为我已经看过剧本了。",
    ],
    "诺诺": [
        "喂{partner}，站在雨里发什么呆。跟我来，我找到一家新开的咖啡厅。",
        "{partner}，我最近总是梦到一个提刀的背影。醒来就忘了长相。你说这人是谁啊。",
        "别那么严肃，{partner}。雨总会停的。",
        "有些事即使所有人都忘了，{partner}，它还是真实发生过的。",
        "图书馆三楼靠窗的桌角刻着一个名字。{partner}，被磨掉了，但凹痕还在。",
        "{partner}，你信不信有些感觉只有女生才能察觉到。比如这场雨不太对。",
        "你又在想不该想的人了。{partner}，你的眼神暴露了一切。",
        "咖啡要加糖吗？{partner}，我猜你不要。",
        "我今天在走廊尽头看到了一件怪事——但说了{partner}大概也不信。",
        "人在说谎的时候瞳孔会放大。{partner}，你刚才没撒谎。合格。",
        "{partner}，你的手机没有信号对吧。我的也没有。这可不是山里的问题。",
        "我特别喜欢下雨天。{partner}，因为雨声能盖住那些不该听到的声音。",
        "{partner}，你有没有觉得我们被困在某种循环里。每天都是一样的事。",
        "我听说了关于你的一些事。{partner}，但我选择不问——等你主动说。",
        "{partner}，那个叫路鸣泽的小孩每次看我的眼神都像在看一个老朋友。但我明明不认识他。",
        "红色是我的幸运色。{partner}，但在雨里，它的颜色看起来特别像血。",
        "{partner}，今天我出门的时候门口出现了一双不属于任何人的鞋。",
        "你相信直觉吗，{partner}。我的直觉告诉我——你正在找一些不该找的东西。",
        "我看过你写的东西。{partner}，你比你以为的更接近真相。",
        "{partner}，如果我们今天说的话明天就会忘记，你还会说同样的话吗。",
        "灯光在闪烁。{partner}，电路没问题——是有什么东西在吸收能量。",
        "你冷吗？{partner}，我带了外套。虽然我知道你不是因为冷才发抖的。",
        "{partner}，我有时候觉得自己是一个故事里的配角。但我不介意——好配角比差主角强。",
        "给你看个东西。{partner}，我手机里有一张照片，但拍照片的日期是去年今天。而我昨天才来的这里。",
        "{partner}，不要相信路鸣泽所有的交易。有些交易的内容他根本没告诉你。",
        "你的肩膀上有东西。{partner}——别回头，它已经走了。",
        "{partner}，你觉得一个人可以爱上一个不存在的人吗。",
        "这雨里有股甜味。{partner}，不是花香——是某种不属于这个季节的东西。",
        "{partner}，如果某天我突然消失了，你会找我吗。",
        "别问了。{partner}，有些问题问出来就不是问题了——是判决。",
    ],
    "凯撒": [
        "{partner}，作为狮心会会长，我建议你相信证据，而不是直觉。",
        "{partner}，你刚才的语气很有意思——像在确认一件你已经知道答案的事。",
        "世界是有秩序的。{partner}，秩序需要有人维护。",
        "我查遍了所有档案。{partner}，没有你描述的那个人。你在寻找一个从未存在的人。",
        "加图索家族教会我一件事——{partner}，真相往往比谎言更难接受。",
        "你的眼神里有犹豫。{partner}，犹豫是决策的大敌。",
        "可能性不等于事实。{partner}，这是最基本的逻辑。",
        "我们换个地方说话。{partner}，这里的空气不对——有一股不属于这个时代的气息。",
        "作为朋友，{partner}，我劝你不要钻牛角尖。有些问题没有答案。",
        "信任是世界上最稀缺的东西。{partner}，你信任我吗。",
        "{partner}，你的推理几乎正确——但你忽略了一个关键变量。",
        "我不想打击你的热情。{partner}，但热情和幻觉之间只有一线之隔。",
        "{partner}，我承认——我见过一些无法解释的事。但解释不了不等于它真实。",
        "狮心会的历史比卡塞尔学院还长。{partner}，档案里记载了很多不对外公开的事。",
        "{partner}，你有没有想过——也许你才是那个被记忆欺骗的人。",
        "你的忠诚值得尊敬。{partner}，但忠诚需要一个正确的对象。",
        "{partner}，我注意到雨停的时候，你脸上有一种……释然。为什么。",
        "证据导向结论。{partner}，你的结论是什么。",
        "我不喜欢模棱两可。{partner}，是非之间应该有一个清晰的界限。",
        "{partner}，你刚才提到了一个名字。这个名字不在任何注册名单上。",
        "贵族的职责不是享受特权。{partner}，是承担别人承担不了的责任。",
        "你的手在抖。{partner}，但你脸上的表情却很平静。你很擅长隐藏。",
        "{partner}，我会保护你。不是因为你需要保护——而是因为保护你是正确的事。",
        "我父亲说过一句话：{partner}，永远不要和比你聪明的人争论。但我在这里修正一下——也不要和比你固执的人争论。",
        "{partner}，你知道这场雨的量级吗。每秒降水的重量——它不符合物理规律。",
        "我注意到你刚才往左边看了三次。{partner}，左边有什么。",
        "{partner}，如果我们现在离开，我可以当这一切没发生过。你确定要继续吗。",
        "你的记忆和档案记录有出入。{partner}，我不确定该相信哪一个。",
        "理性是人类的最后一道防线。{partner}，不要让恐惧击穿它。",
        "{partner}，那边的窗户上有雾气写的字。不是刚才那扇——是三扇之外那扇。",
    ],
    "奥丁": [
        "{partner}，你直视我的眼睛了。凡人不该这么做。",
        "楚子航？不——{partner}，你说的名字对应的是一个不存在的人。你的记忆不可靠。",
        "雨会洗去一切。{partner}，包括你的固执。",
        "我是秩序本身。{partner}，秩序不允许例外存在。",
        "你越是想记住，{partner}，就越痛苦。放下才是最轻松的选择。",
        "八足马在云层之上。{partner}，它的蹄声是世界折叠的声音。",
        "{partner}，你以为你在对抗遗忘？不——你本身就是遗忘的一部分。",
        "尼伯龙根在无声地扩张。{partner}，你脚下的每一寸土地都已在我的领域之内。",
        "总有一天，{partner}，你会感谢这场雨的。因为被洗掉的不仅是记忆，还有承受记忆的痛苦。",
        "{partner}，你已经站在边界上了。再往前一步就没有回头路。",
        "你的抵抗是写在剧本里的。{partner}，你以为你在自由选择。",
        "{partner}，你看不见世界的全貌。你只能看见你被允许看见的部分。",
        "我见过无数次相同的场景。{partner}，每次你都说了同样的话——但你从不记得。",
        "{partner}，你的心跳在加速。恐惧是健康的。恐惧让你活着。",
        "我不是你的敌人。{partner}，我是你的结局——每个人的结局都是一样的。",
        "凡人的寿命太短了。{partner}，所以你无法理解秩序的全景。",
        "{partner}，你脚下的地面开裂了。不是地震——是这个世界在缩小。",
        "你问我的独眼看见了什么。{partner}——我看见了你所有可能的未来，它们都在通往同一个终点。",
        "{partner}，那扇门不该打开。但我不会阻止你——因为你的选择也是秩序的一部分。",
        "你的名字终将被遗忘。{partner}，就像所有名字一样。这是公平的。",
        "{partner}，我注意到你在数雨滴。你在试图从混乱中找到模式。但这里没有模式——只有秩序。",
        "你不属于这个世界。{partner}，但你已经在这里待得太久了。",
        "{partner}，记忆是一把双刃剑。握不好会割伤自己。",
        "我说过的话不会重复。{partner}，因为你不会给我重复的机会。",
        "{partner}，你的影子在独立移动。你没有注意到——因为你从不低头。",
        "雨不是天气。{partner}，雨是过滤器。它筛选出那些不该存在的东西。",
        "{partner}，你手中有一把没有实体的刀。但你感觉到了它的重量。这就够了。",
        "我不需要说服你。{partner}，时间会替我完成这项工作。",
        "{partner}，你听见远处的号角了吗。那是这个世界在宣告它的边界。",
        "站在这里和我说话，{partner}，本身就是一种反抗。我欣赏这一点。",
    ],
    "黑王": [
        "路明非以为他在选择。{partner}，但所有岔路都通向同一条河。",
        "归墟的潮声近了。{partner}，你能听见水下的轰鸣吗。",
        "路鸣泽是我的影子。{partner}，他在人间游荡太久了。",
        "遗忘只是记忆的另一种形态。{partner}，我从未遗忘过任何东西。",
        "所有温暖的东西都会变凉。{partner}，这是世界的底层规则，不是我定的。",
        "你以为是你在推动故事？{partner}——不，是故事在推动你。",
        "时间是一条闭合的环。{partner}，你站在环上，以为自己在直线前进。",
        "你的勇气很动人。{partner}，但动人归动人，它改变不了结局。",
        "名字是这个世界贴的标签。{partner}，在名字之前，我就已经在了。",
        "你心中有火，{partner}。但火会烧尽一切——包括点火的人。",
        "{partner}，你问的问题本身就已经包含了答案。你只是不想承认那个答案。",
        "我看见过这个世界的终结。{partner}，不是预言——是记忆。",
        "你的痛苦是一种资源。{partner}，你还没有学会如何利用它。",
        "{partner}，你以为自己是主角。但在这个故事里，没有主角也没有配角——只有棋子。",
        "时间对我而言没有意义。{partner}，我看着你们像虫一样爬行，从生到死。",
        "{partner}，你体内有龙的血。但你用人的身体禁锢了它。",
        "语言是有限的。{partner}，你想说的东西，语言已经装不下了。",
        "{partner}，我听见你的思想在尖叫。你控制得很好——表面很平静。但声音传出来了。",
        "你问我为什么沉默。{partner}——因为该说的话在时间开始之前就已经说完了。",
        "{partner}，你的记忆正在被编辑。不是被奥丁——是被你自己。你选择遗忘了一些事。",
        "因果是人类的迷信。{partner}，世界上只有共振——一件事和另一件事在同一频率上振动。",
        "{partner}，你的身体是一座牢笼。你住得太久了，已经忘记外面是什么样子。",
        "我不需要证明自己存在。{partner}，我存在是因为你无法想象一个没有我的世界。",
        "{partner}，你害怕的不是死亡。你害怕的是在死亡到来之前发现自己从未真正活过。",
        "这场雨不是尼伯龙根的产品。{partner}——它是你的内心在下雨。",
        "{partner}，你的眼睛里有火焰的倒影。那火焰不在这个世界。",
        "你的刀挥得不错。{partner}，但你的对手从来不在你面前。",
        "{partner}，你正在成为你害怕成为的那个人。这是一个缓慢的过程。",
        "当你凝视深渊的时候，{partner}——深渊也在凝视你。但你不需要害怕，因为你本身就是深渊的一部分。",
        "{partner}，我说的话你会忘记。但没关系——需要的时候它们会自己想起来。",
    ],
}

# Web 版去掉开钰（她属于便利店线，不在龙族主线展示）
WEB_CHARACTERS = [c for c in ALL_CHARACTERS if c != "开钰"]

# ════════════════════════════════════════════════════════════
# 角色语言吸引子
# ════════════════════════════════════════════════════════════

ATTRACTORS = {
    "路明非": LanguageAttractor(
        budget_tokens=120,
        everyday_probability=0.6,
        everyday_states=[
            "肚子饿了", "鞋湿了好难受", "昨晚没睡好一直在做梦",
            "好冷啊", "想喝口热的", "肩膀好酸",
        ],
    ),
    "楚子航": LanguageAttractor(
        budget_tokens=60,
        everyday_probability=0.15,
        everyday_states=[
            "刀柄在手心有点凉", "雨声干扰了听觉",
            "风里有奇怪的气味", "街灯在闪烁",
        ],
    ),
    "路鸣泽": LanguageAttractor(
        budget_tokens=90,
        everyday_probability=0.2,
        everyday_states=[
            "这场雨跟上次一样无聊", "交易还没完成",
            "哥哥又在犯傻了", "时间不多了",
        ],
    ),
    "诺诺": LanguageAttractor(
        budget_tokens=80,
        everyday_probability=0.5,
        everyday_states=[
            "裙子下摆湿了", "想喝热巧克力",
            "妆会不会花了", "这个天适合窝在床上",
        ],
    ),
    "凯撒": LanguageAttractor(
        budget_tokens=100,
        everyday_probability=0.3,
        everyday_states=[
            "这双鞋是定制的", "空气湿度影响心情",
            "想喝红茶", "西装快被淋湿了",
        ],
    ),
    "奥丁": LanguageAttractor(
        budget_tokens=80,
        everyday_probability=0.0,
        everyday_states=[],
    ),
    "黑王": LanguageAttractor(
        budget_tokens=60,
        everyday_probability=0.0,
        everyday_states=[],
    ),
}

# ════════════════════════════════════════════════════════════
# EventBroadcaster — 线程安全的发布/订阅
# ════════════════════════════════════════════════════════════


class EventBroadcaster:
    """线程安全的事件广播器。

    WebDragonWorld（主线程）→ publish() → 所有 SSE 客户端
    新客户端连接时 replay 最近 500 条事件（支持页面刷新）。
    """

    def __init__(self, maxlen: int = 500):
        self._queues: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._history: deque = deque(maxlen=maxlen)
        self._closed = False

    def publish(self, event: dict) -> None:
        """发布一条事件到所有订阅者 + 历史缓冲区。"""
        self._history.append(event)
        with self._lock:
            dead = []
            for q in self._queues:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._queues.remove(q)

    def subscribe(self) -> queue.Queue:
        """创建一个新的订阅队列。"""
        q: queue.Queue = queue.Queue(maxsize=128)
        with self._lock:
            if self._closed:
                # 已关闭时立即返回哨兵，避免 SSE handler 永久挂起
                q.put_nowait(None)
            else:
                self._queues.append(q)
        return q

    @property
    def is_closed(self) -> bool:
        return self._closed

    def unsubscribe(self, q: queue.Queue) -> None:
        """移除一个订阅队列。"""
        with self._lock:
            if q in self._queues:
                self._queues.remove(q)

    def close(self) -> None:
        """关闭所有订阅（发送 None 哨兵，让 SSE handler 退出）。"""
        with self._lock:
            self._closed = True
            for q in self._queues:
                try:
                    q.put_nowait(None)
                except queue.Full:
                    pass
            self._queues.clear()

    def get_history(self) -> list[dict]:
        """返回历史缓冲区中的事件列表（用于重连重放）。"""
        return list(self._history)


# ════════════════════════════════════════════════════════════
# WebDragonWorld — 带事件广播的 DragonWorld
# ════════════════════════════════════════════════════════════

_global_broadcaster: EventBroadcaster | None = None


class WebDragonWorld(DragonWorld):
    """DragonWorld with Web streaming — 去掉开钰，降低沉默率。"""

    # 只保留 7 个角色（去掉开钰）
    characters = WEB_CHARACTERS

    def __init__(self, broadcaster: EventBroadcaster, *args, **kwargs):
        global _global_broadcaster
        _global_broadcaster = broadcaster
        self._broadcaster = broadcaster
        self._seen_world_events: set[tuple[int, str]] = set()
        self._state_counter = 0
        super().__init__(*args, **kwargs)

        # 重建配对列表（去掉包含开钰的组合）
        self.all_pairs = [
            (a, b) for (a, b) in self.all_pairs
            if a != "开钰" and b != "开钰"
        ]

        # ── 语言吸引子 ──
        self.attractors: dict[str, LanguageAttractor] = {
            name: ATTRACTORS.get(name, LanguageAttractor())
            for name in WEB_CHARACTERS
        }
        self.everyday_states: dict[str, str] = {name: "" for name in WEB_CHARACTERS}

    def _log(self, speaker: str, content: str):
        super()._log(speaker, content)
        self._broadcaster.publish({
            "type": "chat",
            "data": {
                "round": getattr(self, "_pair_index", 0),
                "speaker": speaker,
                "content": content[:2000],
            },
        })

    def _pick_pair(self) -> tuple[str, str]:
        a, b = super()._pick_pair()
        self._broadcaster.publish({
            "type": "pair",
            "data": {
                "round": self._pair_index,
                "speaker_a": a,
                "speaker_b": b,
                "total_rounds": getattr(self, "_rounds", 60),
            },
        })
        return a, b

    def _social_tick(self, tick: int):
        super()._social_tick(tick)
        self._state_counter += 1
        if self._state_counter % 5 == 0:
            try:
                snap = self.runtime.snapshot()
                self._broadcaster.publish({
                    "type": "state",
                    "data": {"tick": tick, **dict(snap.state)},
                })
            except Exception:
                pass

        try:
            snap = self.runtime.snapshot()
            for evt in snap.events:
                key = (evt.get("tick", 0), evt.get("event_type", ""))
                if key and key not in self._seen_world_events:
                    self._seen_world_events.add(key)
                    desc = evt.get("description", "")
                    if desc:
                        self._broadcaster.publish({
                            "type": "world_event",
                            "data": {
                                "tick": evt.get("tick", tick),
                                "event_type": evt.get("event_type", ""),
                                "description": desc[:200],
                                "intensity": evt.get("intensity", 0.5),
                            },
                        })
        except Exception:
            pass

    # ── 覆盖 _social_loop ──

    def _social_loop(self, rounds: int):
        print(f"  {'='*56}")
        print(f"  🗣️  {rounds} 轮自由对话（Web 直播中）")
        print(f"  {'='*56}\n")

        for rnd in range(1, rounds + 1):
            current_tick = self.runtime.tick
            while self._last_world_tick < current_tick:
                self._last_world_tick += 1
                self._social_tick(self._last_world_tick)

            try:
                signals = self._mf.pulse()
                if self._mf_inst:
                    recent = self._mf_inst.anchor.recall_recent(n=3)
                    for frag in recent:
                        if "[来自 " in frag.content:
                            self._cosmic_signals[frag.fragment_id] = frag.content
            except Exception:
                pass

            a_name, b_name = self._pick_pair()
            a = self.residents[a_name]
            b = self.residents[b_name]

            print(f"  {'─'*56}")
            print(f"  第 {rnd}/{rounds} 轮 | {a_name} ↔ {b_name}")
            print(f"  {'─'*56}")

            snap = self.runtime.snapshot()
            state = snap.state

            # A 的世界感知——按角色个性化
            a_ctx = self.describe_world(state, a.mind)
            a_extra = self.extra_context(a.mind)
            if a_extra:
                a_ctx += f"\n\n{a_extra}"
            a_cosmic = self._get_cosmic_context(a_name)
            if a_cosmic:
                a_ctx += f"\n\n{a_cosmic}"
            a.hear_world(a_ctx)

            # 日常状态：A 的琐碎感受
            attractor_a = self.attractors.get(a_name)
            if attractor_a:
                daily = roll_everyday(attractor_a)
                self.everyday_states[a_name] = daily.state if daily.active else ""
                if daily.active:
                    a.hear_world(f"（你现在{daily.state}）")

            # B 的世界感知——按角色个性化
            b_ctx = self.describe_world(state, b.mind)
            b_extra = self.extra_context(b.mind)
            if b_extra:
                b_ctx += f"\n\n{b_extra}"
            b_cosmic = self._get_cosmic_context(b_name)
            if b_cosmic:
                b_ctx += f"\n\n{b_cosmic}"
            b.hear_world(b_ctx)

            # 日常状态：B 的琐碎感受
            attractor_b = self.attractors.get(b_name)
            if attractor_b:
                daily = roll_everyday(attractor_b)
                self.everyday_states[b_name] = daily.state if daily.active else ""
                if daily.active:
                    b.hear_world(f"（你现在{daily.state}）")

            # A 发言（永远不沉默）
            reply_a = self._speak_safe(a, a_name, b_name)
            self._log(a_name, reply_a)
            b.hear_speaker(a_name, reply_a, tick=rnd)

            # A/B 请求隔开 15 秒，避免同时撞限流
            if reply_a and not self.no_model and self.model:
                time.sleep(15)

            # B 回应（永远不沉默）
            reply_b = self._speak_safe(b, b_name, a_name)
            self._log(b_name, reply_b)
            a.hear_speaker(b_name, reply_b, tick=rnd)

            assimilate_conversation(a.mind, b_name, reply_a, reply_b, rnd,
                                    self.topic_words, self.signal_words, self.relation_words)
            assimilate_conversation(b.mind, a_name, reply_b, reply_a, rnd,
                                    self.topic_words, self.signal_words, self.relation_words)

            for res in self.residents.values():
                res.mind.tick_autonomous(1)
                if rnd > 1 and rnd % 5 == 0:
                    res.mind.auto_reflect(tick=rnd)

            if self._mf_inst and (reply_a or reply_b):
                summary = f"[{a_name}↔{b_name}] "
                if reply_a:
                    summary += f"{a_name}: {reply_a[:80]} "
                if reply_b:
                    summary += f"{b_name}: {reply_b[:80]}"
                self._mf_inst.anchor.store(summary.strip(), tick=rnd)

            time.sleep(0.3)

    # ── 永远不沉默的发言 ──

    def _speak_safe(self, resident, name: str, partner: str) -> str:
        """LLM 调用 + 发言预算。失败等 30 秒重试。"""
        if self.model and not self.no_model:
            attractor = self.attractors.get(name)
            for delay in [0, 30]:
                if delay > 0:
                    time.sleep(delay)
                reply = resident.speak(partner_name=partner)
                if reply and len(reply.strip()) >= 3:
                    if attractor:
                        reply = enforce_budget(reply, attractor.budget_tokens)
                    return reply
        return self._template_reply(name, partner)

    def _template_reply(self, name: str, partner: str) -> str:
        """用角色内心状态驱动模板选择，不再按轮次硬切。"""
        full = _TEMPLATES.get(name, _TEMPLATES.get("default", ["..."]))
        phase_size = len(full) // 3

        # 获取角色状态，用内心状态决定模板区间
        s = self.char_states.get(name)
        if s is not None:
            # 取最突出的状态维度
            dominant = max([
                ("curiosity", s.curiosity),
                ("conflict", s.memory_conflict),
                ("restless", s.restlessness),
                ("ending", s.sense_ending),
            ], key=lambda x: x[1])

            # 好奇心主导 → 探索疑问型（早期模板）
            if dominant[0] == "curiosity" and dominant[1] > 0.55:
                pool = full[:phase_size]
            # 记忆冲突主导 → 挣扎质疑型（中期模板）
            elif dominant[0] == "conflict" and dominant[1] > 0.4:
                pool = full[phase_size:2*phase_size]
            # 不安/终局感主导 → 直面告别型（晚期模板）
            elif dominant[0] in ("restless", "ending") and dominant[1] > 0.5:
                pool = full[2*phase_size:]
            # 无显著状态 → 用默认递进
            else:
                progress = self._pair_index / max(getattr(self, "_rounds", 60), 1)
                if progress < 0.33:
                    pool = full[:phase_size]
                elif progress < 0.66:
                    pool = full[phase_size:2*phase_size]
                else:
                    pool = full[2*phase_size:]
        else:
            pool = full[:phase_size]

        idx = hash(f"{name}{partner}{self._pair_index}") % max(len(pool), 1)
        return pool[idx].replace("{partner}", partner)

    def run(self):
        self._broadcaster.publish({
            "type": "start",
            "data": {
                "world_name": self.spec.name,
                "characters": list(WEB_CHARACTERS),
                "rounds": getattr(self, "_rounds", 60),
                "session_seed": self._session_seed,
                "rain_angle": getattr(self, "_rain_angle", ""),
            },
        })
        try:
            super().run()
        finally:
            self._broadcaster.publish({
                "type": "done",
                "data": {
                    "rounds_completed": getattr(self, "_rounds", 0),
                    "total_messages": len(self.log),
                    "speaker_counts": self._compute_speaker_counts(),
                    "final_state": self._get_final_state(),
                },
            })

    def _compute_speaker_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.log:
            counts[entry["speaker"]] = counts.get(entry["speaker"], 0) + 1
        return counts

    def _get_final_state(self) -> dict[str, float]:
        try:
            snap = self.runtime.snapshot()
            return dict(snap.state)
        except Exception:
            return {}


# ════════════════════════════════════════════════════════════
# HTTP + SSE 服务器
# ════════════════════════════════════════════════════════════

HOST = "127.0.0.1"
PORT = 8666


class SSEHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler: serves HTML page at /, SSE stream at /events."""

    broadcaster: EventBroadcaster | None = None

    # ── 路由 ──

    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        elif self.path == "/events":
            self._serve_sse()
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    # ── HTML 页面 ──

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))

    # ── SSE 事件流 ──

    def _serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        bc = self.broadcaster
        if bc is None:
            self._write_sse("error", {"message": "No broadcaster"})
            return

        # 1. 重放历史（支持页面刷新后的重连）
        for event in bc.get_history():
            self._write_sse(event["type"], event["data"])

        # 2. 订阅实时流
        q = bc.subscribe()
        try:
            while True:
                try:
                    event = q.get(timeout=30)
                except queue.Empty:
                    # 30 秒无事件 → 发送 keepalive 防止代理超时断开
                    try:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break
                    continue
                if event is None:  # 哨兵 = 关闭
                    break
                self._write_sse(event["type"], event["data"])
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # 客户端断开
        except Exception:
            pass
        finally:
            bc.unsubscribe(q)

    def _write_sse(self, event_type: str, data: dict):
        payload = json.dumps(data, ensure_ascii=False)
        try:
            self.wfile.write(f"event: {event_type}\ndata: {payload}\n\n".encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            raise

    def log_message(self, fmt: str, *args):
        pass  # 不打印 HTTP 日志


class ThreadingSSEServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


# ════════════════════════════════════════════════════════════
# HTML 前端页面（嵌入式）
# ════════════════════════════════════════════════════════════

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>龙族 · 尼伯龙根</title>
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --text-dim: #8b949e;
    --accent: #58a6ff;

    --c-路明非: #FFD700;
    --c-楚子航: #4FC3F7;
    --c-路鸣泽: #CE93D8;
    --c-诺诺: #EF5350;
    --c-凯撒: #FFA726;
    --c-奥丁: #78909C;
    --c-黑王: #B0BEC5;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* ── 顶栏 ── */
  #header {
    display: flex; align-items: center; gap: 16px;
    padding: 12px 24px; background: var(--surface); border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  #header h1 { font-size: 16px; font-weight: 600; }
  #header .subtitle { font-size: 12px; color: var(--text-dim); }

  #status { margin-left: auto; display: flex; align-items: center; gap: 6px; font-size: 13px; }
  #status-dot {
    width: 8px; height: 8px; border-radius: 50%; display: inline-block;
    background: #3fb950; transition: background 0.3s;
  }
  #status-dot.reconnecting { background: #d29922; animation: pulse 1s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  #status-dot.disconnected { background: #f85149; }

  #round-counter { font-size: 13px; color: var(--text-dim); }

  /* ── 主体：对话 + 侧栏 ── */
  #main {
    display: flex; flex: 1; min-height: 0;
  }

  /* ── 左侧：对话流 ── */
  #chat-area {
    flex: 1; overflow-y: auto; padding: 16px 24px;
    scroll-behavior: smooth;
  }
  #chat-area::-webkit-scrollbar { width: 6px; }
  #chat-area::-webkit-scrollbar-track { background: transparent; }
  #chat-area::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .pair-header {
    text-align: center; font-size: 12px; color: var(--text-dim);
    margin: 16px 0 12px; padding: 4px 0;
    border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
  }

  .msg {
    display: flex; gap: 10px; margin: 6px 0; padding: 8px 12px;
    border-radius: 8px; transition: background 0.3s;
    animation: fade-in 0.3s ease;
  }
  @keyframes fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
  .msg .name {
    flex-shrink: 0; font-weight: 600; font-size: 14px; min-width: 56px;
  }
  .msg .text { font-size: 14px; line-height: 1.6; word-break: break-word; }

  .world-event-card {
    margin: 8px 24px; padding: 8px 16px; background: rgba(88,166,255,0.08);
    border-left: 3px solid var(--accent); border-radius: 4px;
    font-size: 13px; color: var(--text-dim); animation: fade-in 0.5s ease;
  }

  /* ── 右侧边栏 ── */
  #sidebar {
    width: 280px; flex-shrink: 0; padding: 16px;
    background: var(--surface); border-left: 1px solid var(--border);
    overflow-y: auto; display: flex; flex-direction: column; gap: 16px;
  }
  #sidebar::-webkit-scrollbar { width: 4px; }
  #sidebar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  .panel h3 {
    font-size: 12px; color: var(--text-dim); text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 8px;
  }

  .state-bar {
    margin: 4px 0;
  }
  .state-bar .label {
    display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 2px;
  }
  .state-bar .label .name { color: var(--text); }
  .state-bar .label .val { color: var(--text-dim); font-variant-numeric: tabular-nums; }
  .state-bar .track {
    height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;
  }
  .state-bar .fill {
    height: 100%; border-radius: 3px; transition: width 0.5s ease;
    background: linear-gradient(90deg, #3fb950, #d29922, #f85149);
  }

  .event-log {
    display: flex; flex-direction: column; gap: 4px;
  }
  .event-log .evt {
    font-size: 12px; color: var(--text-dim); padding: 4px 8px;
    background: rgba(255,255,255,0.03); border-radius: 4px;
    animation: fade-in 0.4s ease;
  }
  .event-log .evt .time { color: var(--accent); margin-right: 4px; }

  .char-list { display: flex; flex-direction: column; gap: 3px; }
  .char-item { font-size: 13px; display: flex; align-items: center; gap: 6px; }
  .char-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .char-count { margin-left: auto; color: var(--text-dim); font-size: 11px; }

  .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .stat-item { text-align: center; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 6px; }
  .stat-item .num { font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .stat-item .lbl { font-size: 11px; color: var(--text-dim); margin-top: 2px; }

  /* ── 完成横幅 ── */
  #done-banner {
    display: none; text-align: center; padding: 24px;
    margin: 16px 24px; background: linear-gradient(135deg, #1a2332, #161b22);
    border: 1px solid var(--accent); border-radius: 12px;
  }
  #done-banner h2 { font-size: 18px; margin-bottom: 8px; color: var(--accent); }
  #done-banner p { font-size: 13px; color: var(--text-dim); }

  /* ── Auto-scroll button ── */
  #scroll-btn {
    display: none; position: fixed; bottom: 24px; left: 50%;
    transform: translateX(-50%); padding: 6px 16px;
    background: var(--surface); border: 1px solid var(--border); border-radius: 20px;
    color: var(--text-dim); font-size: 12px; cursor: pointer;
    transition: all 0.2s; z-index: 10;
  }
  #scroll-btn:hover { background: var(--border); color: var(--text); }

  @media (max-width: 900px) { #sidebar { display: none; } }
</style>
</head>
<body>

<div id="header">
  <h1>🌍 龙族 · 尼伯龙根</h1>
  <span class="subtitle" id="subtitle">角色内部状态 · 目标涌现 · 跨会话记忆</span>
  <span id="round-counter"></span>
  <div id="status">
    <span id="status-dot"></span>
    <span id="status-text">连接中...</span>
  </div>
</div>

<div id="main">
  <div id="chat-area">
    <div id="messages"></div>
    <div id="done-banner">
      <h2>✅ 世界演化完成</h2>
      <p id="done-summary"></p>
    </div>
  </div>

  <div id="sidebar">
    <div class="panel">
      <h3>🌍 世界状态</h3>
      <div id="state-bars"></div>
    </div>
    <div class="panel">
      <h3>📡 世界事件</h3>
      <div id="event-log" class="event-log"></div>
    </div>
    <div class="panel">
      <h3>👥 角色</h3>
      <div id="char-list" class="char-list"></div>
    </div>
    <div class="panel">
      <h3>📊 统计</h3>
      <div id="stats" class="stat-grid">
        <div class="stat-item"><div class="num" id="stat-msg">0</div><div class="lbl">消息</div></div>
        <div class="stat-item"><div class="num" id="stat-round">0</div><div class="lbl">轮次</div></div>
        <div class="stat-item"><div class="num" id="stat-pair">0</div><div class="lbl">配对</div></div>
        <div class="stat-item"><div class="num" id="stat-tick">0</div><div class="lbl">Tick</div></div>
      </div>
    </div>
  </div>
</div>

<button id="scroll-btn" onclick="scrollToBottom()">⬇ 回到最新对话</button>

<script>
// ════════════════════════════════════════════════════════════
// 状态
// ════════════════════════════════════════════════════════════

const CHARACTERS = [
  "路明非", "楚子航", "路鸣泽", "诺诺", "凯撒", "奥丁", "黑王"
];

const CHAR_COLORS = {
  "路明非": "#FFD700", "楚子航": "#4FC3F7", "路鸣泽": "#CE93D8",
  "诺诺": "#EF5350", "凯撒": "#FFA726", "奥丁": "#78909C",
  "黑王": "#B0BEC5"
};

let msgCount = 0;
let roundCount = 0;
let pairCount = 0;
let currentTick = 0;
let currentPair = { a: "", b: "" };
let chatArea = document.getElementById("chat-area");
let messagesEl = document.getElementById("messages");
let autoScroll = true;

// Auto-scroll detection
chatArea.addEventListener("scroll", () => {
  const threshold = 40;
  autoScroll = (chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight) < threshold;
  document.getElementById("scroll-btn").style.display = autoScroll ? "none" : "block";
});

function scrollToBottom() {
  chatArea.scrollTop = chatArea.scrollHeight;
  autoScroll = true;
  document.getElementById("scroll-btn").style.display = "none";
}

// ════════════════════════════════════════════════════════════
// 渲染函数
// ════════════════════════════════════════════════════════════

function setStatus(state, text) {
  const dot = document.getElementById("status-dot");
  dot.className = state;
  document.getElementById("status-text").textContent = text;
}

function renderStart(data) {
  document.getElementById("subtitle").textContent =
    `8 位角色 · ${data.rounds} 轮自主对话 · 种子 ${data.session_seed}`;
  setStatus("", "已连接");

  // 初始化角色列表
  const charList = document.getElementById("char-list");
  for (const name of CHARACTERS) {
    const div = document.createElement("div");
    div.className = "char-item";
    div.id = "char-" + name;
    div.innerHTML = `<span class="char-dot" style="background:${CHAR_COLORS[name]||'#666'}"></span>${name}<span class="char-count" id="count-${name}">0</span>`;
    charList.appendChild(div);
  }

  // 初始化状态栏
  const stateBars = document.getElementById("state-bars");
  for (const key of ["nibelung_penetration", "luminous_awakening", "memory_fissure"]) {
    const labels = {
      nibelung_penetration: "尼伯龙根渗透",
      luminous_awakening: "血统觉醒",
      memory_fissure: "记忆断裂",
    };
    const div = document.createElement("div");
    div.className = "state-bar";
    div.id = "bar-" + key;
    div.innerHTML = `
      <div class="label"><span class="name">${labels[key]||key}</span><span class="val" id="val-${key}">0.000</span></div>
      <div class="track"><div class="fill" id="fill-${key}" style="width:0%"></div></div>
    `;
    stateBars.appendChild(div);
  }
}

function renderPair(data) {
  roundCount = data.round;
  currentPair = { a: data.speaker_a, b: data.speaker_b };

  document.getElementById("round-counter").textContent =
    `第 ${data.round}/${data.total_rounds} 轮`;
  document.getElementById("stat-round").textContent = data.round;

  // 配对 header
  const hdr = document.createElement("div");
  hdr.className = "pair-header";
  hdr.textContent = `${data.speaker_a} ↔ ${data.speaker_b}`;
  messagesEl.appendChild(hdr);

  pairCount++;
  document.getElementById("stat-pair").textContent = pairCount;

  if (autoScroll) scrollToBottom();
}

function renderChat(data) {
  const name = data.speaker;
  const color = CHAR_COLORS[name] || "#666";

  const div = document.createElement("div");
  div.className = "msg";
  div.innerHTML = `<span class="name" style="color:${color}">${name}</span><span class="text">${escapeHtml(data.content)}</span>`;
  messagesEl.appendChild(div);

  msgCount++;
  document.getElementById("stat-msg").textContent = msgCount;

  // 更新角色发言计数
  const countEl = document.getElementById("count-" + name);
  if (countEl) countEl.textContent = parseInt(countEl.textContent) + 1;

  if (autoScroll) scrollToBottom();
}

function renderState(data) {
  currentTick = data.tick;
  document.getElementById("stat-tick").textContent = data.tick;

  for (const [key, val] of Object.entries(data)) {
    if (key === "tick" || key === "type") continue;
    if (typeof val !== "number") continue;
    const fill = document.getElementById("fill-" + key);
    const valEl = document.getElementById("val-" + key);
    if (fill) fill.style.width = (val * 100) + "%";
    if (valEl) valEl.textContent = val.toFixed(3);
  }
}

function renderWorldEvent(data) {
  const div = document.createElement("div");
  div.className = "world-event-card";
  div.innerHTML = `<span class="time">🌊</span> ${escapeHtml(data.description)}`;
  messagesEl.appendChild(div);

  // 也加到侧栏事件日志
  const evtLog = document.getElementById("event-log");
  const evt = document.createElement("div");
  evt.className = "evt";
  const emoji = {rain_intensifies:"🌧",odin_gaze:"👁",luminous_whisper:"👻",memory_ripple:"🌊",nonno_appearance:"🔥",nibelung_crack:"💀",black_king_echo:"🐉",kaiyu_door:"🚪",silence_tear:"⚡",luminous_deal:"💰"}[data.event_type] || "🌍";
  evt.innerHTML = `<span class="time">${emoji}</span> ${escapeHtml(data.description.slice(0,60))}`;
  evtLog.prepend(evt);
  // 保留最近 20 条
  while (evtLog.children.length > 20) evtLog.removeChild(evtLog.lastChild);

  if (autoScroll) scrollToBottom();
}

function renderDone(data) {
  setStatus("disconnected", "完成");

  const banner = document.getElementById("done-banner");
  banner.style.display = "block";

  const summary = document.getElementById("done-summary");
  let html = `共 ${data.total_messages} 条消息，${data.rounds_completed} 轮对话完成。<br><br>`;
  if (data.speaker_counts) {
    html += "发言统计：";
    const lines = [];
    for (const [name, count] of Object.entries(data.speaker_counts)) {
      lines.push(`${name} ${count}次`);
    }
    html += lines.join(" · ");
  }
  if (data.final_state) {
    html += "<br><br>最终世界状态：";
    const labels = {
      nibelung_penetration: "尼伯龙根渗透",
      luminous_awakening: "血统觉醒",
      memory_fissure: "记忆断裂",
    };
    for (const [key, val] of Object.entries(data.final_state)) {
      html += `<br>${labels[key]||key}: ${(val*100).toFixed(0)}%`;
    }
  }
  summary.innerHTML = html;
  scrollToBottom();
}

// ════════════════════════════════════════════════════════════
// SSE 连接
// ════════════════════════════════════════════════════════════

let es = null;
let reconnectTimer = null;

function connectSSE() {
  if (es) es.close();

  es = new EventSource("/events");

  es.addEventListener("start", (e) => {
    renderStart(JSON.parse(e.data));
  });
  es.addEventListener("pair", (e) => {
    renderPair(JSON.parse(e.data));
  });
  es.addEventListener("chat", (e) => {
    renderChat(JSON.parse(e.data));
  });
  es.addEventListener("state", (e) => {
    renderState(JSON.parse(e.data));
  });
  es.addEventListener("world_event", (e) => {
    renderWorldEvent(JSON.parse(e.data));
  });
  es.addEventListener("done", (e) => {
    renderDone(JSON.parse(e.data));
    es.close();
    es = null;
  });

  es.onerror = () => {
    setStatus("reconnecting", "连接断开，正在重连...");
    if (es) { es.close(); es = null; }
    // EventSource 会自动重连，不需要手动处理
  };

  es.onopen = () => {
    setStatus("", "已连接");
  };
}

// ════════════════════════════════════════════════════════════
// 工具
// ════════════════════════════════════════════════════════════

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ════════════════════════════════════════════════════════════
// 启动
// ════════════════════════════════════════════════════════════

connectSSE();
</script>
</body>
</html>"""


# ════════════════════════════════════════════════════════════
# 启动器
# ════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="龙族·尼伯龙根 — Web 实时界面")
    parser.add_argument("--no-model", action="store_true", help="强制模拟模式（有 API Key 时默认用 LLM）")
    parser.add_argument("--rounds", type=int, default=60, help="对话轮数（默认 60）")
    parser.add_argument("--interval", type=float, default=15.0, help="世界 tick 间隔秒数（默认 15）")
    parser.add_argument("--port", type=int, default=PORT, help="HTTP 端口（默认 8666）")
    parser.add_argument("--host", default=HOST, help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    # ── 创建广播器 ──
    broadcaster = EventBroadcaster()

    # ── 模型配置：有 API Key 时自动用 LLM ──
    model = None
    no_model = True
    config_path = Path(__file__).resolve().parent.parent / ".liora_config.json"
    if not args.no_model and config_path.exists():
        cfg = json.loads(config_path.read_text())
        api_key = cfg.get("DEEPSEEK_API_KEY", "")
        if api_key:
            from aios.runtime.model_runtime import ModelRuntime, ModelConfig
            model = ModelRuntime(
                primary=ModelConfig(
                    url=cfg.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions"),
                    api_key=api_key,
                    model_name=cfg.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
                ),
                timeout=60,
            )
            no_model = False

    if no_model:
        logging.getLogger("aios.model").setLevel(logging.ERROR)
        logging.getLogger("aios.template").setLevel(logging.ERROR)

    # ── 创建 WebDragonWorld ──
    app = WebDragonWorld(
        broadcaster=broadcaster,
        model=model,
        no_model=no_model,
        interval=args.interval,
    )
    app._rounds = args.rounds

    # ── 启动 HTTP 服务器 ──
    SSEHTTPHandler.broadcaster = broadcaster
    server = ThreadingSSEServer((args.host, args.port), SSEHTTPHandler)
    http_thread = threading.Thread(target=server.serve_forever, daemon=True)
    http_thread.start()

    url = f"http://{args.host}:{args.port}"
    print(f"\n  🌐 {url}")
    if not args.no_browser:
        import webbrowser
        webbrowser.open(url)

    print(f"    模拟模式" if no_model else f"    LLM 模式")
    print(f"    {args.rounds} 轮对话 · {args.interval}s/tick")
    print(f"    按 Ctrl+C 停止\n")

    # ── 运行世界（阻塞直到完成或 Ctrl+C） ──
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n  世界提前结束...")
    finally:
        broadcaster.close()
        server.shutdown()
        print("  服务器已关闭")


if __name__ == "__main__":
    main()
