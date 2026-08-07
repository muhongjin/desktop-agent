from desktop_agent.main import build_argument_parser


def test_argument_parser_only_exposes_safe_mode():
    parser = build_argument_parser()
    args = parser.parse_args([])

    assert args.safe_mode is False
    assert not hasattr(args, "port")
    assert not hasattr(args, "login")
