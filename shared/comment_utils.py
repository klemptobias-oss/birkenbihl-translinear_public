import logging
import traceback

logger = logging.getLogger(__name__)

def safe_discover_and_attach_comments(blocks, preprocess_module,
                                      comment_regexes=None,
                                      strip_comment_lines=True,
                                      pipeline_name="pipeline"):
    """
    Safely call preprocess.discover_and_attach_comments and always return a list
    of blocks (never None). On error, return the original blocks with empty
    'comments' and 'comment_token_mask' fields ensured.
    """
    try:
        if not blocks:
            return list(blocks) if blocks is not None else []

        # Call the real function if present
        func = getattr(preprocess_module, "discover_and_attach_comments", None)
        if callable(func):
            # Try calling with optional parameters if they exist
            import inspect
            sig = inspect.signature(func)
            params = {}
            if 'comment_regexes' in sig.parameters and comment_regexes is not None:
                params['comment_regexes'] = comment_regexes
            if 'strip_comment_lines' in sig.parameters and strip_comment_lines is not None:
                params['strip_comment_lines'] = strip_comment_lines
            
            if params:
                final_blocks = func(blocks, **params)
            else:
                final_blocks = func(blocks)
        else:
            logger.debug("%s: preprocess has no discover_and_attach_comments, returning original blocks", pipeline_name)
            final_blocks = list(blocks)

        # Normalise None -> list
        if final_blocks is None:
            logger.debug("%s: discover_and_attach_comments returned None -> using original blocks", pipeline_name)
            final_blocks = list(blocks)

        # Ensure fields exist
        for b in final_blocks:
            if 'comments' not in b:
                b['comments'] = []
            if 'comment_token_mask' not in b or b.get('comment_token_mask') is None:
                gtokens = b.get('gr_tokens') or []
                b['comment_token_mask'] = [False] * len(gtokens)

        found = sum(len(b.get('comments', [])) for b in final_blocks)
        logger.debug("%s: returning %d blocks with comments found=%d", pipeline_name, len(final_blocks), found)
        return final_blocks

    except Exception as e:
        tb = traceback.format_exc()
        logger.error("%s: discover_and_attach_comments failed: %s", pipeline_name, str(e))
        logger.debug("%s: traceback (first 800 chars):\n%s", pipeline_name, tb[:800])
        safe_blocks = list(blocks) if blocks else []
        for b in safe_blocks:
            b.setdefault('comments', [])
            if 'comment_token_mask' not in b or b.get('comment_token_mask') is None:
                gtokens = b.get('gr_tokens') or []
                b['comment_token_mask'] = [False] * len(gtokens)
        logger.debug("%s: returning original blocks with comments=[]", pipeline_name)
        return safe_blocks

