"""Direct Gmail cleanup script: delete unread mail and empty trash without OpenAI."""
from gmail_client import empty_trash, get_gmail_service, search_unread, search_spam, trash_unread_spam_messages


def main():
    service = get_gmail_service()

    unread_ids = search_unread(service, max_results=500)
    print(f"Found {len(unread_ids)} unread emails.")

    spam_ids = search_spam(service, max_results=500)
    print(f"Found {len(spam_ids)} spam emails.")

    trash_result = trash_unread_spam_messages(service, unread_ids + spam_ids)
    print(
        f"Moved unread or spam emails to Trash: {trash_result['trashed_count']} moved, "
        f"{trash_result['failed_count']} failed."
    )

    delete_result = empty_trash(service)
    print(
        f"Permanently deleted from Trash: {delete_result['deleted_count']} removed, "
        f"{delete_result['failed_count']} failed."
    )


if __name__ == "__main__":
    main()
