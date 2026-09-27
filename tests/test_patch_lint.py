"""The Cemu patch lint (tools/patch_lint.py)."""
import unittest

from tools.patch_lint import lint


class PatchLintTests(unittest.TestCase):
    def test_a_label_defined_twice_is_refused_as_cemu_does(self):
        source = "[G]\napMessageText:\n.int 0\napMessageText:\nblr\n"
        self.assertEqual(len(lint(source)), 1)
        self.assertIn("apMessageText", lint(source)[0])

    def test_an_undefined_label_is_refused(self):
        for line in ("b nowhere", "bne nowhere", ".int nowhere", "lis r3, nowhere@ha",
                     "0x02346d50 = b nowhere"):
            with self.subTest(line=line):
                self.assertEqual(len(lint(f"[G]\nhere:\n{line}\n")), 1)

    def test_labels_are_scoped_by_group_and_numbers_are_not_labels(self):
        source = ("[A]\nx:\nb x\nbeq 0x02346d54\n.int 0x41504d41\n.int -1\n"
                  "moduleMatches = 0x6267BFD0\n.origin = codecave\nlwz r3, 4(r1)\n"
                  "[B]\nx:\nlis r4, x@ha\naddi r4, r4, x@l\n")
        self.assertEqual(lint(source), [])

    def test_the_composed_message_patch_is_clean(self):
        from tools import build_native_from_source as native
        from tools.build_message_action import compose_executor_hooks
        from tools.message_submission import compose_submission
        generated = native.generate(resource_gate=True, event_gate=True)
        for name, raw in generated.items():
            if name.endswith(".asm"):
                with self.subTest(patch=name):
                    self.assertEqual(lint(raw.decode("utf-8")), [])
        item = generated["runtime/patch_apInject.asm"].decode("utf-8")
        self.assertEqual(lint(compose_submission(compose_executor_hooks(item))), [])


if __name__ == "__main__":
    unittest.main()
