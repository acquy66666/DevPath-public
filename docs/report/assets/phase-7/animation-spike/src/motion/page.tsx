import { CELEBRATE, REST } from "../_gen/naomi";
import { NaomiMotion } from "../_parts/naomi-motion";
import { Stage } from "../_parts/stage";

export default function Page() {
  return (
    <Stage variant="motion">
      <NaomiMotion celebrate={CELEBRATE} rest={REST} />
    </Stage>
  );
}
