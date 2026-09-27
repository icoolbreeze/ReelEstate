// Remotion CLI config. Project props & public dir are passed by pipeline/render.py:
//   --props=<project>/output/_render_props.json --public-dir=<project>
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
