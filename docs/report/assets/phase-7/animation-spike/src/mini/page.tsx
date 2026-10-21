import { CELEBRATE, REST } from "../_gen/naomi";
import { NaomiMini } from "../_parts/naomi-mini";
import { Stage } from "../_parts/stage";

export default function Page() {
  return (
    <Stage variant="mini">
      <NaomiMini celebrate={CELEBRATE} rest={REST} />
    </Stage>
  );
}
