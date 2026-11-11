# 知识口播系列

用于知识、政策和市场分析。各期目录为 epNN-<slug>，与房源、小ONE会客厅共用正式发布号。编号由 `npm run episodes` 计算，不在这里写死下一期。

新建：npm run new -- knowledge <slug> --topic <选题> --city 成都。

生产交接见 docs/PRODUCTION.md，先运行 npm run doctor；按 docs/RUNBOOK-knowledge-koubo.md 准备事实来源、分段稿、配音、数字人及素材，然后用统一的 check、still、render 命令。知识类没有房源编号、地图和 POI 生产步骤。

公共代码、字体品牌和 Node 依赖共用；各期 script、broll、voice、heygen、matte、out、consent、data、public、work 独立。
