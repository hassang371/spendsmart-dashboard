import unittest
from unittest.mock import MagicMock, patch
import sys
import torch  # Added
import os  # Restored

sys.path.append(os.getcwd())

from packages.categorization import cli


class TestCLIDDatabase(unittest.TestCase):
    @patch("packages.categorization.cli.create_client")
    @patch("packages.categorization.cli.HypCDTrainer")
    @patch("packages.categorization.cli.SentenceTransformer")
    def test_train_db(self, mock_bert, mock_trainer, mock_create_client):
        # Setup mocks
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase

        # Mock DB response
        mock_response = MagicMock()
        mock_response.data = [
            {"description": "Uber Ride", "category": "Transport", "is_manual": True},
            {"description": "Swiggy", "category": "Food", "is_manual": True},
        ]
        # Mock Query Chain (table -> select -> eq -> eq -> execute)
        mock_query = MagicMock()
        mock_supabase.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query  # Chaining returns same object
        mock_query.execute.return_value = mock_response

        # Mock Args
        args = MagicMock()
        args.user_id = "test-user-id"
        args.epochs = 1

        # Mock Metrics
        mock_trainer.return_value.train_supervised.return_value = {"loss": [0.5, 0.1]}

        # Call function
        try:
            cli.train_db(args)
        except AttributeError:
            self.fail("train_db not implemented")

        # Verify Supabase was queried
        mock_supabase.table.assert_called_with("transactions")

        # Verify Trainer was initialized and trained
        mock_trainer.assert_called()
        mock_trainer.return_value.train_supervised.assert_called()

    @patch("packages.categorization.cli.create_client")
    @patch("packages.categorization.cli.HyperbolicProjector")
    @patch("packages.categorization.cli.SentenceTransformer")
    def test_classify_db(self, mock_bert, mock_proj, mock_create_client):
        # Setup mocks
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase

        # Mock DB response for Uncategorized
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "txn1", "description": "Uber", "category": "Uncategorized"},
            {"id": "txn2", "description": "Zomato", "category": "Uncategorized"},
        ]

        # Mock Query Chain
        mock_query = MagicMock()
        mock_supabase.table.return_value.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = mock_response

        # Mock Projector Behavior
        mock_p_instance = mock_proj.return_value
        # projector(embs) -> Tensor
        mock_p_instance.return_value = torch.randn(2, 2)
        # manifold.dist() -> Tensor (flat)
        mock_p_instance.manifold.dist.return_value = torch.tensor([0.1, 0.8])

        # Mock Model Loading
        # Assume HypCDClassifier/Projector loading works or is mocked
        # We need to mock the prediction logic.
        # classify_db likely uses HypCDClassifier.predict or predict_batch

        with patch("packages.categorization.cli.HypCDClassifier") as mock_clf_cls:
            mock_clf = mock_clf_cls.return_value
            # Set anchors
            mock_clf.anchors = {
                "Transport": torch.randn(1, 2),
                "Food": torch.randn(1, 2),
            }
            # predict_batch returns [(cat, conf, vec), ...]
            mock_clf.predict_batch.return_value = [
                ("Transport", 0.9, None),
                ("Food", 0.8, None),
            ]

            args = MagicMock()
            args.user_id = "u1"

            try:
                cli.classify_db(args)
            except AttributeError:
                self.fail("classify_db not implemented")

            # Verify Supabase Update called
            # Should update each transaction
            # mock_supabase.table("transactions").update(...).eq("id", ...).execute()
            self.assertTrue(mock_supabase.table.return_value.update.called)

            # Check calls
            # We expect update({"category": "Transport"}).eq("id", "txn1")
            # We can inspect calls
            update_calls = mock_supabase.table.return_value.update.call_args_list
            self.assertEqual(len(update_calls), 2)


if __name__ == "__main__":
    unittest.main()
